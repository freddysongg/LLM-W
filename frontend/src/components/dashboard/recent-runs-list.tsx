import * as React from "react";
import { Link } from "react-router-dom";
import type { Run, RunStatus } from "@/types/run";
import { RunRow, RunRowCell } from "@/components/shared/run-row";
import { StatusDot } from "@/components/shared/status-dot";
import type { RunStatus as DotStatus } from "@/components/shared/status-dot";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";

interface RecentRunsListProps {
  readonly runs: ReadonlyArray<Run>;
}

const MAX_RECENT = 5;

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

function formatDuration({
  startedAt,
  completedAt,
}: {
  readonly startedAt: string | null;
  readonly completedAt: string | null;
}): string {
  if (!startedAt) return "—";
  const start = new Date(startedAt).getTime();
  const end = completedAt ? new Date(completedAt).getTime() : Date.now();
  const seconds = Math.max(0, Math.floor((end - start) / 1000));
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  if (hours > 0) return `${hours}h ${(minutes % 60).toString().padStart(2, "0")}m`;
  if (minutes > 0) return `${minutes}m ${(seconds % 60).toString().padStart(2, "0")}s`;
  return `${seconds}s`;
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

function runLabel(run: Run): string {
  return `run ${run.id.slice(0, 6)}`;
}

export function RecentRunsList({ runs }: RecentRunsListProps): React.JSX.Element {
  const recent = React.useMemo<ReadonlyArray<Run>>(() => {
    return [...runs]
      .sort(
        (left, right) => new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime(),
      )
      .slice(0, MAX_RECENT);
  }, [runs]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Recent runs</CardTitle>
        <Link to="/runs" className="font-mono text-[11px] text-ink-3 no-underline hover:text-ink-1">
          View all →
        </Link>
      </CardHeader>
      {recent.length === 0 ? (
        <div className="px-[18px] py-6 text-center font-mono text-[11px] text-ink-3">
          No runs yet.
        </div>
      ) : (
        <div>
          {recent.map((run) => (
            <RunRow key={run.id} className="grid-cols-[16px_1fr_90px_90px] px-[18px]">
              <StatusDot status={mapStatus(run.status)} />
              <div className="min-w-0">
                <div className="truncate text-[12.5px] font-medium text-ink-1">{runLabel(run)}</div>
                <div className="font-mono text-[10.5px] text-ink-3">{run.id}</div>
              </div>
              <RunRowCell>
                {formatDuration({ startedAt: run.startedAt, completedAt: run.completedAt })}
              </RunRowCell>
              <RunRowCell align="end">{formatRelative(run.startedAt ?? run.createdAt)}</RunRowCell>
            </RunRow>
          ))}
        </div>
      )}
    </Card>
  );
}
