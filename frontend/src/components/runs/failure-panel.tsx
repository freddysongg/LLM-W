import * as React from "react";
import type { Run } from "@/types/run";

interface FailurePanelProps {
  readonly run: Run;
}

export function FailurePanel({ run }: FailurePanelProps): React.JSX.Element | null {
  if (run.status !== "failed") return null;

  return (
    <div className="rounded-lg border border-destructive/50 bg-destructive/5 p-4 space-y-3">
      <div className="flex items-center gap-2">
        <div className="h-2 w-2 rounded-full bg-destructive" />
        <span className="text-sm font-semibold text-destructive">Run Failed</span>
      </div>

      {run.failureStage && (
        <div className="text-xs">
          <span className="text-muted-foreground">Failed at stage: </span>
          <span className="font-mono">{run.failureStage.replace(/_/g, " ")}</span>
        </div>
      )}

      {run.failureReason && (
        <div className="space-y-1">
          <div className="text-xs font-medium text-destructive">Error</div>
          <pre className="text-xs text-muted-foreground bg-muted rounded px-3 py-2 whitespace-pre-wrap overflow-x-auto font-mono">
            {run.failureReason}
          </pre>
        </div>
      )}

      {run.lastCheckpointPath && (
        <div className="text-xs">
          <span className="text-muted-foreground">Last checkpoint: </span>
          <span className="font-mono">{run.lastCheckpointPath}</span>
        </div>
      )}
    </div>
  );
}
