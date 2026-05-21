import * as React from "react";
import { MoreHorizontal, Trash2 } from "lucide-react";
import { useModalGpus } from "@/hooks/useCatalog";
import type { ModalGpuOption } from "@/types/catalog";
import type { Run, RunStatus } from "@/types/run";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { RunRow, RunRowActions, RunRowCell } from "@/components/shared/run-row";
import { StatusDot } from "@/components/shared/status-dot";
import type { RunStatus as DotStatus } from "@/components/shared/status-dot";

interface RunListProps {
  readonly runs: ReadonlyArray<Run>;
  readonly selectedRunId: string | null;
  readonly onSelectRun: (runId: string) => void;
  readonly onDeleteRun: (runId: string) => void;
  readonly isDeletingRunId: string | null;
  readonly onStartRun?: () => void;
  readonly isStartingRun?: boolean;
  readonly canStartRun?: boolean;
}

const DELETABLE_STATUSES = new Set<RunStatus>(["completed", "failed", "cancelled"]);
const RUN_ROW_COLUMNS = "grid-cols-[16px_1fr_150px_120px_90px_100px_32px]";

function mapStatus(status: RunStatus): DotStatus {
  switch (status) {
    case "running":
      return "running";
    case "completed":
      return "success";
    case "failed":
      return "failed";
    case "paused":
    case "fallback_pending":
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

function environmentLabel({
  run,
  gpuOptions,
}: {
  run: Run;
  gpuOptions: ReadonlyArray<ModalGpuOption> | undefined;
}): string {
  if (!run.environment || run.environment === "local") return "local";
  const option =
    run.modalGpuType && gpuOptions
      ? (gpuOptions.find(({ gpuType }) => gpuType === run.modalGpuType) ?? null)
      : null;
  return option ? `modal · ${option.label.toLowerCase()}` : "modal";
}

function stepsLabel(run: Run): string {
  const step = run.currentStep.toLocaleString();
  const total = run.totalSteps !== null ? run.totalSteps.toLocaleString() : "—";
  return `${step}/${total}`;
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

function statusTag(status: RunStatus): React.ReactNode {
  switch (status) {
    case "running":
      return <Badge variant="running">LIVE</Badge>;
    case "paused":
      return (
        <Badge variant="warn" dot={false}>
          PAUSED
        </Badge>
      );
    case "failed":
      return (
        <Badge variant="danger" dot={false}>
          FAILED
        </Badge>
      );
    default:
      return null;
  }
}

export function RunList({
  runs,
  selectedRunId,
  onSelectRun,
  onDeleteRun,
  isDeletingRunId,
}: RunListProps): React.JSX.Element {
  const { data: gpuOptions } = useModalGpus();
  if (runs.length === 0) {
    return (
      <Card>
        <div className="flex flex-col items-center gap-3 py-12 font-mono text-[11px] text-ink-3">
          No runs yet.
        </div>
      </Card>
    );
  }

  return (
    <Card>
      <RunRow isHeader className={`${RUN_ROW_COLUMNS} px-[18px]`}>
        <span />
        <span>Run</span>
        <span>Environment</span>
        <span>Progress</span>
        <span className="text-right">Started</span>
        <span />
        <span />
      </RunRow>
      {runs.map((run) => {
        const isSelected = selectedRunId === run.id;
        const isDeletable = DELETABLE_STATUSES.has(run.status);
        return (
          <RunRow
            key={run.id}
            className={`${RUN_ROW_COLUMNS} px-[18px]`}
            selected={isSelected}
            onClick={() => onSelectRun(run.id)}
          >
            <StatusDot status={mapStatus(run.status)} />
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="truncate text-[12.5px] font-medium text-ink-1">
                  run {run.id.slice(0, 6)}
                </span>
                {statusTag(run.status)}
              </div>
              <div className="font-mono text-[10.5px] text-ink-3">{run.id}</div>
            </div>
            <RunRowCell>{environmentLabel({ run, gpuOptions })}</RunRowCell>
            <RunRowCell>{stepsLabel(run)}</RunRowCell>
            <RunRowCell align="end">{formatRelative(run.startedAt ?? run.createdAt)}</RunRowCell>
            <RunRowActions>
              {isDeletable ? (
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 text-ink-3 hover:text-[color:var(--danger)]"
                  disabled={isDeletingRunId === run.id}
                  onClick={(event) => {
                    event.stopPropagation();
                    onDeleteRun(run.id);
                  }}
                  aria-label="Delete run"
                >
                  <Trash2 className="size-3.5" aria-hidden="true" />
                </Button>
              ) : null}
            </RunRowActions>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 text-ink-3 opacity-0 group-hover:opacity-100"
              onClick={(event) => event.stopPropagation()}
              aria-label="More actions"
            >
              <MoreHorizontal className="size-3.5" aria-hidden="true" />
            </Button>
          </RunRow>
        );
      })}
    </Card>
  );
}
