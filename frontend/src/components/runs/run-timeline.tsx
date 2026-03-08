import * as React from "react";
import type { RunStage } from "@/types/run";

interface RunTimelineProps {
  readonly stages: ReadonlyArray<RunStage>;
  readonly selectedStageId: string | null;
  readonly onSelectStage: (stageId: string) => void;
}

function stageDurationLabel(durationMs: number | null): string {
  if (durationMs === null) return "";
  const seconds = Math.round(durationMs / 1000);
  if (seconds < 60) return `${seconds}s`;
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}

function stageStatusColor(status: RunStage["status"]): string {
  switch (status) {
    case "completed":
      return "bg-green-500";
    case "running":
      return "bg-blue-500 animate-pulse";
    case "failed":
      return "bg-destructive";
    case "skipped":
      return "bg-muted-foreground";
    case "pending":
      return "bg-muted border border-muted-foreground/30";
    default: {
      const _exhaustive: never = status;
      return _exhaustive;
    }
  }
}

function stageTextColor(status: RunStage["status"]): string {
  switch (status) {
    case "completed":
      return "text-green-600";
    case "running":
      return "text-blue-600 font-medium";
    case "failed":
      return "text-destructive font-medium";
    case "skipped":
      return "text-muted-foreground";
    case "pending":
      return "text-muted-foreground";
    default: {
      const _exhaustive: never = status;
      return _exhaustive;
    }
  }
}

export function RunTimeline({
  stages,
  selectedStageId,
  onSelectStage,
}: RunTimelineProps): React.JSX.Element {
  if (stages.length === 0) {
    return <div className="py-6 text-center text-sm text-muted-foreground">No stage data yet.</div>;
  }

  const sorted = [...stages].sort((a, b) => a.stageOrder - b.stageOrder);

  return (
    <div className="space-y-1">
      {sorted.map((stage, idx) => (
        <button
          key={stage.id}
          type="button"
          onClick={() => onSelectStage(stage.id)}
          className={`w-full flex items-center gap-3 px-3 py-2 rounded-md text-left transition-colors ${
            selectedStageId === stage.id ? "bg-accent" : "hover:bg-muted/50"
          }`}
        >
          <div className="flex items-center gap-2 shrink-0">
            <span className="text-xs text-muted-foreground w-4 text-right">{idx + 1}</span>
            <div className={`h-3 w-3 rounded-full ${stageStatusColor(stage.status)}`} />
          </div>

          <span className={`text-sm flex-1 ${stageTextColor(stage.status)}`}>
            {stage.stageName.replace(/_/g, " ")}
          </span>

          <span className="text-xs text-muted-foreground shrink-0">
            {stageDurationLabel(stage.durationMs)}
          </span>
        </button>
      ))}
    </div>
  );
}
