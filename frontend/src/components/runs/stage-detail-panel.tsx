import * as React from "react";
import type { RunStage } from "@/types/run";
import { Badge } from "@/components/ui/badge";

interface StageDetailPanelProps {
  readonly stage: RunStage;
  readonly onClose: () => void;
}

function formatTimestamp(ts: string | null): string {
  if (!ts) return "—";
  return new Date(ts).toLocaleTimeString();
}

function formatDuration(ms: number | null): string {
  if (ms === null) return "—";
  const seconds = Math.round(ms / 1000);
  if (seconds < 60) return `${seconds}s`;
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}

type BadgeVariant = "default" | "secondary" | "destructive" | "outline";

function statusVariant(status: RunStage["status"]): BadgeVariant {
  switch (status) {
    case "completed":
      return "secondary";
    case "running":
      return "default";
    case "failed":
      return "destructive";
    case "skipped":
    case "pending":
      return "outline";
    default: {
      const _exhaustive: never = status;
      return _exhaustive;
    }
  }
}

export function StageDetailPanel({ stage, onClose }: StageDetailPanelProps): React.JSX.Element {
  return (
    <div className="border rounded-lg bg-card p-4 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold">{stage.stageName.replace(/_/g, " ")}</h3>
          <Badge variant={statusVariant(stage.status)}>{stage.status}</Badge>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="text-xs text-muted-foreground hover:text-foreground"
        >
          close
        </button>
      </div>

      <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
        <div>
          <span className="text-muted-foreground">Started</span>
          <div>{formatTimestamp(stage.startedAt)}</div>
        </div>
        <div>
          <span className="text-muted-foreground">Completed</span>
          <div>{formatTimestamp(stage.completedAt)}</div>
        </div>
        <div>
          <span className="text-muted-foreground">Duration</span>
          <div>{formatDuration(stage.durationMs)}</div>
        </div>
      </div>

      {stage.warnings.length > 0 && (
        <div className="space-y-1">
          <div className="text-xs font-medium text-yellow-600">Warnings</div>
          <ul className="space-y-1">
            {stage.warnings.map((warning, idx) => (
              <li key={idx} className="text-xs text-muted-foreground">
                {warning}
              </li>
            ))}
          </ul>
        </div>
      )}

      {stage.outputSummary && (
        <div className="space-y-1">
          <div className="text-xs font-medium">Output Summary</div>
          <div className="text-xs text-muted-foreground whitespace-pre-wrap font-mono bg-muted rounded px-2 py-2">
            {stage.outputSummary}
          </div>
        </div>
      )}

      {stage.logTail && (
        <div className="space-y-1">
          <div className="text-xs font-medium">Log Tail</div>
          <pre className="text-xs text-muted-foreground bg-muted rounded px-2 py-2 overflow-x-auto whitespace-pre-wrap">
            {stage.logTail}
          </pre>
        </div>
      )}
    </div>
  );
}
