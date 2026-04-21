import * as React from "react";
import { RotateCcw } from "lucide-react";
import { useNavigate } from "react-router-dom";
import type { Run, RunStatus } from "@/types/run";
import type { RunSummary } from "@/types/run-summary";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { RunRow, RunRowActions, RunRowCell } from "@/components/shared/run-row";
import { RunHistorySparkline } from "@/components/runs/run-history-sparkline";
import { StatusDot } from "@/components/shared/status-dot";
import type { RunStatus as DotStatus } from "@/components/shared/status-dot";

interface TrainingHistoryTabProps {
  readonly runs: ReadonlyArray<Run>;
  readonly summariesByRun: ReadonlyMap<string, RunSummary>;
  readonly onRerun: (run: Run) => void;
}

const HISTORY_ROW_COLUMNS = "grid-cols-[16px_1fr_110px_1fr_80px_100px]";

function mapStatus(status: RunStatus): DotStatus {
  switch (status) {
    case "running":
      return "running";
    case "completed":
      return "success";
    case "failed":
      return "failed";
    case "paused":
      return "paused";
    case "pending":
    case "cancelled":
      return "pending";
    default: {
      const _exhaustive: never = status;
      return _exhaustive;
    }
  }
}

function formatRelative(iso: string | null): string {
  if (!iso) return "—";
  const delta = Date.now() - new Date(iso).getTime();
  const minutes = Math.round(delta / 60000);
  if (minutes < 1) return "now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}

export function TrainingHistoryTab({
  runs,
  summariesByRun,
  onRerun,
}: TrainingHistoryTabProps): React.JSX.Element {
  const navigate = useNavigate();

  if (runs.length === 0) {
    return (
      <Card>
        <div className="py-10 text-center font-mono text-[11px] text-ink-3">
          No previous training runs.
        </div>
      </Card>
    );
  }

  return (
    <Card>
      <RunRow isHeader className={`${HISTORY_ROW_COLUMNS} px-[18px]`}>
        <span />
        <span>Run</span>
        <span>Steps</span>
        <span>Loss</span>
        <span className="text-right">Started</span>
        <span />
      </RunRow>
      {runs.map((run) => {
        const summary = summariesByRun.get(run.id);
        return (
          <RunRow
            key={run.id}
            className={`${HISTORY_ROW_COLUMNS} px-[18px]`}
            onClick={() => void navigate(`/runs`)}
          >
            <StatusDot status={mapStatus(run.status)} />
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="truncate text-[12.5px] font-medium text-ink-1">
                  run {run.id.slice(0, 6)}
                </span>
                <Badge variant="secondary" dot={false}>
                  {run.status}
                </Badge>
              </div>
              <div className="font-mono text-[10.5px] text-ink-3">{run.id}</div>
            </div>
            <RunRowCell>
              {run.currentStep.toLocaleString()}
              {run.totalSteps ? ` / ${run.totalSteps.toLocaleString()}` : ""}
            </RunRowCell>
            <RunRowCell>
              {summary !== undefined ? <RunHistorySparkline summary={summary} /> : "—"}
            </RunRowCell>
            <RunRowCell align="end">{formatRelative(run.startedAt ?? run.createdAt)}</RunRowCell>
            <RunRowActions>
              <Button
                size="sm"
                variant="outline"
                onClick={(event) => {
                  event.stopPropagation();
                  onRerun(run);
                }}
              >
                <RotateCcw className="size-3" aria-hidden="true" />
                Re-run
              </Button>
            </RunRowActions>
          </RunRow>
        );
      })}
    </Card>
  );
}
