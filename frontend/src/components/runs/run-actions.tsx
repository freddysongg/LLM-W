import * as React from "react";
import type { Run } from "@/types/run";
import { Button } from "@/components/ui/button";

interface RunActionsProps {
  readonly run: Run;
  readonly onCancel: () => void;
  readonly onPause: () => void;
  readonly onResume: () => void;
  readonly isCancelling: boolean;
  readonly isPausing: boolean;
  readonly isResuming: boolean;
}

export function RunActions({
  run,
  onCancel,
  onPause,
  onResume,
  isCancelling,
  isPausing,
  isResuming,
}: RunActionsProps): React.JSX.Element {
  const { status } = run;
  const canCancel = status === "running" || status === "paused" || status === "pending";
  const canPause = status === "running";
  const canResume = status === "paused" || status === "failed";

  if (!canCancel && !canPause && !canResume) return <></>;

  return (
    <div className="flex items-center gap-2">
      {canPause && (
        <Button variant="outline" size="sm" onClick={onPause} disabled={isPausing}>
          {isPausing ? "Pausing…" : "Pause"}
        </Button>
      )}

      {canResume && (
        <Button variant="outline" size="sm" onClick={onResume} disabled={isResuming}>
          {isResuming ? "Resuming…" : "Resume"}
        </Button>
      )}

      {canCancel && (
        <Button variant="destructive" size="sm" onClick={onCancel} disabled={isCancelling}>
          {isCancelling ? "Cancelling…" : "Cancel"}
        </Button>
      )}
    </div>
  );
}
