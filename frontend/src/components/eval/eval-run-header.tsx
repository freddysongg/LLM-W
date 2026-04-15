import * as React from "react";
import type { EvalRun, EvalRunStatus } from "@/types/eval";
import { Badge } from "@/components/ui/badge";

interface EvalRunHeaderProps {
  readonly evalRun: EvalRun;
}

type BadgeVariant = "default" | "secondary" | "destructive" | "outline";

function statusVariant(status: EvalRunStatus): BadgeVariant {
  switch (status) {
    case "running":
    case "pending":
      return "default";
    case "completed":
      return "secondary";
    case "failed":
      return "destructive";
    case "cancelled":
      return "outline";
    default: {
      const exhaustive: never = status;
      return exhaustive;
    }
  }
}

function formatUsd(amount: number): string {
  return `$${amount.toFixed(4)}`;
}

function formatTimestamp(timestamp: string | null): string {
  if (timestamp === null) return "—";
  return new Date(timestamp).toLocaleString();
}

function formatPassRate(passRate: number | null): string {
  if (passRate === null) return "—";
  return `${Math.round(passRate * 100)}%`;
}

export function EvalRunHeader({ evalRun }: EvalRunHeaderProps): React.JSX.Element {
  const { id, status, passRate, totalCostUsd, maxCostUsd, startedAt, completedAt, trainingRunId } =
    evalRun;
  return (
    <div className="rounded-lg border bg-card p-4 space-y-3">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="font-mono text-sm">{id.slice(0, 12)}</span>
          <Badge variant={statusVariant(status)}>{status}</Badge>
        </div>
        <div className="text-xs text-muted-foreground">
          {trainingRunId ? `training run ${trainingRunId.slice(0, 8)}` : "standalone"}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-4">
        <div>
          <div className="text-xs text-muted-foreground">Pass rate</div>
          <div>{formatPassRate(passRate)}</div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground">Total cost</div>
          <div>{formatUsd(totalCostUsd)}</div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground">Cost cap</div>
          <div>{maxCostUsd !== null ? formatUsd(maxCostUsd) : "—"}</div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground">Started</div>
          <div className="text-xs">{formatTimestamp(startedAt)}</div>
        </div>
      </div>

      {completedAt !== null && (
        <div className="text-xs text-muted-foreground">
          Completed {formatTimestamp(completedAt)}
        </div>
      )}
    </div>
  );
}
