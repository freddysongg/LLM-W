import * as React from "react";
import type { Checkpoint } from "@/types/run";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

interface ResumeFromCheckpointDialogProps {
  readonly isOpen: boolean;
  readonly checkpoints: ReadonlyArray<Checkpoint>;
  readonly onConfirm: (checkpoint: Checkpoint) => void;
  readonly onClose: () => void;
  readonly isResuming: boolean;
}

export function ResumeFromCheckpointDialog({
  isOpen,
  checkpoints,
  onConfirm,
  onClose,
  isResuming,
}: ResumeFromCheckpointDialogProps): React.JSX.Element {
  const [selectedCheckpointId, setSelectedCheckpointId] = React.useState<string | null>(null);

  const sorted = React.useMemo(
    () => [...checkpoints].sort((a, b) => b.step - a.step),
    [checkpoints],
  );

  React.useEffect(() => {
    if (sorted.length > 0) {
      setSelectedCheckpointId(sorted[0].id);
    }
  }, [sorted]);

  const selectedCheckpoint = sorted.find((c) => c.id === selectedCheckpointId) ?? null;

  const handleConfirm = (): void => {
    if (selectedCheckpoint) {
      onConfirm(selectedCheckpoint);
    }
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
          <DialogTitle>Resume from Checkpoint</DialogTitle>
        </DialogHeader>

        <div className="space-y-2 my-2">
          {sorted.length === 0 && (
            <div className="text-sm text-muted-foreground">No checkpoints available.</div>
          )}
          {sorted.map((checkpoint) => (
            <button
              key={checkpoint.id}
              type="button"
              onClick={() => setSelectedCheckpointId(checkpoint.id)}
              className={`w-full flex items-start gap-3 p-3 rounded-md border text-left transition-colors ${
                selectedCheckpointId === checkpoint.id
                  ? "border-primary bg-primary/5"
                  : "border-input hover:bg-muted/50"
              }`}
            >
              <div className="flex-1">
                <div className="text-sm font-medium">Step {checkpoint.step}</div>
                <div className="text-xs text-muted-foreground font-mono truncate">
                  {checkpoint.path}
                </div>
              </div>
            </button>
          ))}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={isResuming}>
            Cancel
          </Button>
          <Button onClick={handleConfirm} disabled={!selectedCheckpoint || isResuming}>
            {isResuming ? "Resuming…" : "Resume"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
