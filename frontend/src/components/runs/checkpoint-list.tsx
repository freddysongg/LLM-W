import * as React from "react";
import { RefreshCcw } from "lucide-react";
import type { Checkpoint } from "@/types/run";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { RunRow, RunRowCell } from "@/components/shared/run-row";
import { StatusDot } from "@/components/shared/status-dot";

interface CheckpointListProps {
  readonly checkpoints: ReadonlyArray<Checkpoint>;
  readonly onSelectCheckpoint: (checkpoint: Checkpoint) => void;
  readonly selectedCheckpointPath: string | null;
}

const CHECKPOINT_ROW_COLUMNS = "grid-cols-[16px_1fr_120px_100px_90px_100px]";

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(0)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

function formatRelative(iso: string): string {
  const delta = Date.now() - new Date(iso).getTime();
  const minutes = Math.round(delta / 60000);
  if (minutes < 1) return "now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}

function totalSizeLabel(checkpoints: ReadonlyArray<Checkpoint>): string {
  const totalBytes = checkpoints.reduce((sum, cp) => sum + cp.sizeBytes, 0);
  return formatBytes(totalBytes);
}

export function CheckpointList({
  checkpoints,
  onSelectCheckpoint,
  selectedCheckpointPath,
}: CheckpointListProps): React.JSX.Element {
  if (checkpoints.length === 0) {
    return (
      <Card>
        <div className="py-6 text-center font-mono text-[11px] text-ink-3">No checkpoints yet.</div>
      </Card>
    );
  }

  const sorted = [...checkpoints].sort((left, right) => right.step - left.step);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Checkpoints</CardTitle>
        <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-ink-3">
          {sorted.length} saved · {totalSizeLabel(sorted)}
        </span>
      </CardHeader>
      {sorted.map((checkpoint) => {
        const isSelected = selectedCheckpointPath === checkpoint.path;
        const isPruned = !checkpoint.isRetained;
        return (
          <RunRow
            key={checkpoint.id}
            className={`${CHECKPOINT_ROW_COLUMNS} px-[18px] ${isPruned ? "opacity-60" : ""}`}
            selected={isSelected}
          >
            <StatusDot status={checkpoint.isBest ? "success" : "pending"} />
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span
                  className={`truncate text-[12.5px] font-medium text-ink-1 ${isPruned ? "line-through" : ""}`}
                >
                  step_{checkpoint.step}.pt
                </span>
                {checkpoint.isBest ? (
                  <Badge variant="success" dot={false}>
                    BEST EVAL
                  </Badge>
                ) : null}
                {isPruned ? (
                  <Badge variant="outline" dot={false}>
                    Pruned
                  </Badge>
                ) : null}
              </div>
              <div className="truncate font-mono text-[10.5px] text-ink-3">{checkpoint.path}</div>
            </div>
            <RunRowCell>{formatBytes(checkpoint.sizeBytes)}</RunRowCell>
            <RunRowCell>{isPruned ? "pruned" : "retained"}</RunRowCell>
            <RunRowCell>{formatRelative(checkpoint.createdAt)}</RunRowCell>
            <div className="flex justify-end">
              <Button
                size="sm"
                variant="outline"
                disabled={isPruned}
                onClick={(event) => {
                  event.stopPropagation();
                  onSelectCheckpoint(checkpoint);
                }}
              >
                <RefreshCcw className="size-3" aria-hidden="true" />
                Resume
              </Button>
            </div>
          </RunRow>
        );
      })}
    </Card>
  );
}
