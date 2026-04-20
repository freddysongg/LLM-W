import * as React from "react";
import { Play, Sparkles } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Callout } from "@/components/shared/callout";
import type { TrainingFormSlice, TrainingMethod } from "@/components/training/training-form";

interface LaunchRunDialogProps {
  readonly isOpen: boolean;
  readonly slice: TrainingFormSlice;
  readonly method: TrainingMethod;
  readonly modelId: string | null;
  readonly datasetId: string | null;
  readonly isLaunching: boolean;
  readonly onLaunch: (params: { readonly runName: string }) => void;
  readonly onClose: () => void;
}

const ESTIMATED_HOURS_PER_EPOCH = 14.2;
const ESTIMATED_COST_PER_HOUR_USD = 2.1;

function formatCost({ hours, rate }: { readonly hours: number; readonly rate: number }): string {
  return `$${(hours * rate).toFixed(2)}`;
}

export function LaunchRunDialog({
  isOpen,
  slice,
  method,
  modelId,
  datasetId,
  isLaunching,
  onLaunch,
  onClose,
}: LaunchRunDialogProps): React.JSX.Element {
  const [runName, setRunName] = React.useState<string>("");

  React.useEffect(() => {
    if (isOpen) {
      const suffix = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 16);
      setRunName(`${method}-ft-${suffix}`);
    }
  }, [isOpen, method]);

  const { training, execution } = slice;
  const estimatedHours = training.epochs * ESTIMATED_HOURS_PER_EPOCH;
  const estimatedCost = formatCost({ hours: estimatedHours, rate: ESTIMATED_COST_PER_HOUR_USD });
  const target =
    execution.environment === "modal" && execution.modalGpuType
      ? `modal · ${execution.modalGpuType}`
      : execution.environment;

  const handleLaunch = (): void => {
    onLaunch({ runName });
  };

  return (
    <Dialog
      open={isOpen}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent className="max-w-[640px]">
        <DialogHeader>
          <DialogTitle>Launch training run</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-4 px-6 py-4">
          <div className="space-y-1.5">
            <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-ink-3">
              Run name
            </span>
            <Input
              mono
              value={runName}
              onChange={(event) => setRunName(event.target.value)}
              placeholder="my-run"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <ReadoutRow label="Base model" value={modelId ?? "—"} />
            <ReadoutRow label="Dataset" value={datasetId ?? "—"} />
            <ReadoutRow label="Method" value={method} />
            <ReadoutRow label="LR" value={training.learningRate.toExponential(2)} />
            <ReadoutRow label="Epochs" value={String(training.epochs)} />
            <ReadoutRow label="Target" value={target} />
          </div>
          <Callout tone="iris" icon={<Sparkles className="size-3.5" aria-hidden="true" />}>
            <span>
              Estimated cost: <strong>{estimatedCost}</strong> · ~{estimatedHours.toFixed(1)}h on{" "}
              {target}
            </span>
          </Callout>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={isLaunching}>
            Cancel
          </Button>
          <Button variant="primary" onClick={handleLaunch} disabled={isLaunching || !runName}>
            <Play aria-hidden="true" />
            {isLaunching ? "Launching…" : "Launch"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

interface ReadoutRowProps {
  readonly label: string;
  readonly value: string;
}

function ReadoutRow({ label, value }: ReadoutRowProps): React.JSX.Element {
  return (
    <div className="flex flex-col gap-1">
      <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-ink-3">{label}</span>
      <span className="rounded-md border border-hairline bg-surface-2 px-3 py-1.5 font-mono text-[11.5px] text-ink-1">
        {value}
      </span>
    </div>
  );
}
