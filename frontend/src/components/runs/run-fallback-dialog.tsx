import * as React from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useRunFallback } from "@/hooks/useRunFallback";
import { useToast } from "@/hooks/use-toast";
import { describeApiError } from "@/lib/api-error";
import type { FallbackProposedPayload } from "@/types/websocket";
import type { ModalGpuOption } from "@/types/catalog";
import type { ModalGpuType } from "@/types/run";

interface RunFallbackDialogProps {
  readonly isOpen: boolean;
  readonly projectId: string;
  readonly runId: string;
  readonly maxRunMinutes: number;
  readonly proposal: FallbackProposedPayload | null;
  readonly onClose: () => void;
}

function formatWorstCaseCost({
  option,
  maxRunMinutes,
}: {
  readonly option: ModalGpuOption;
  readonly maxRunMinutes: number;
}): string {
  const worstCase = (option.rateUsdHr * maxRunMinutes) / 60;
  return `$${worstCase.toFixed(2)}`;
}

export function RunFallbackDialog({
  isOpen,
  projectId,
  runId,
  maxRunMinutes,
  proposal,
  onClose,
}: RunFallbackDialogProps): React.JSX.Element | null {
  const { toast } = useToast();
  const fallback = useRunFallback({ projectId, runId });

  const [selectedGpuType, setSelectedGpuType] = React.useState<ModalGpuType | null>(null);

  React.useEffect(() => {
    if (proposal && proposal.candidates.length > 0) {
      setSelectedGpuType(proposal.candidates[0].gpuType);
    } else {
      setSelectedGpuType(null);
    }
  }, [proposal]);

  if (!proposal) return null;

  const handleAccept = (): void => {
    if (!selectedGpuType) return;
    fallback.mutate(
      { action: "accept", gpuType: selectedGpuType },
      {
        onSuccess: () => {
          toast({
            title: "Fallback accepted",
            description: `Restarting run on ${selectedGpuType}.`,
          });
          onClose();
        },
        onError: (cause) => {
          toast({
            title: "Fallback failed",
            description: describeApiError({
              cause,
              fallback: "Could not accept fallback choice.",
            }),
            variant: "destructive",
          });
        },
      },
    );
  };

  const handleCancel = (): void => {
    fallback.mutate(
      { action: "cancel" },
      {
        onSuccess: () => {
          toast({
            title: "Run cancelled",
            description: "Fallback chain aborted.",
          });
          onClose();
        },
        onError: (cause) => {
          toast({
            title: "Cancel failed",
            description: describeApiError({
              cause,
              fallback: "Could not cancel the fallback proposal.",
            }),
            variant: "destructive",
          });
        },
      },
    );
  };

  return (
    <Dialog
      open={isOpen}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Out-of-memory detected — pick a larger GPU</DialogTitle>
        </DialogHeader>

        <div className="space-y-3 my-2">
          <p className="text-sm text-muted-foreground">
            Attempt {proposal.attemptIndex + 1} on{" "}
            <span className="font-mono">{proposal.fromGpu}</span> ran out of memory (detected via{" "}
            {proposal.detectedVia}). Pick a larger GPU to retry, or cancel the run.
          </p>

          {proposal.candidates.length === 0 ? (
            <div className="text-sm text-destructive">
              No fallback GPUs available within the cost cap.
            </div>
          ) : (
            <div className="space-y-2">
              {proposal.candidates.map((candidate) => (
                <button
                  key={candidate.gpuType}
                  type="button"
                  onClick={() => setSelectedGpuType(candidate.gpuType)}
                  className={`w-full flex items-start gap-3 p-3 rounded-md border text-left transition-colors ${
                    selectedGpuType === candidate.gpuType
                      ? "border-primary bg-primary/5"
                      : "border-input hover:bg-muted/50"
                  }`}
                >
                  <div className="flex-1">
                    <div className="text-sm font-medium">{candidate.label}</div>
                    <div className="text-xs text-muted-foreground font-mono">
                      {candidate.vramGb} GB VRAM · ${candidate.rateUsdHr.toFixed(2)}/hr · worst-case{" "}
                      {formatWorstCaseCost({ option: candidate, maxRunMinutes })}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleCancel} disabled={fallback.isPending}>
            Cancel run
          </Button>
          <Button
            onClick={handleAccept}
            disabled={!selectedGpuType || proposal.candidates.length === 0 || fallback.isPending}
          >
            {fallback.isPending ? "Submitting…" : "Retry with selected GPU"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
