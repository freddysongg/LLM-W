import * as React from "react";
import { Trash2 } from "lucide-react";
import type { Run } from "@/types/run";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

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

type BadgeVariant = "default" | "secondary" | "destructive" | "outline";

function statusVariant(status: Run["status"]): BadgeVariant {
  switch (status) {
    case "running":
      return "default";
    case "completed":
      return "secondary";
    case "failed":
      return "destructive";
    case "cancelled":
    case "paused":
    case "pending":
      return "outline";
    default: {
      const _exhaustive: never = status;
      return _exhaustive;
    }
  }
}

function formatDuration(startedAt: string | null, completedAt: string | null): string {
  if (!startedAt) return "—";
  const end = completedAt ? new Date(completedAt) : new Date();
  const ms = end.getTime() - new Date(startedAt).getTime();
  const seconds = Math.floor(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  if (hours > 0) return `${hours}h ${minutes % 60}m`;
  if (minutes > 0) return `${minutes}m`;
  return `${seconds}s`;
}

const DELETABLE_STATUSES = new Set(["completed", "failed", "cancelled"]);

export function RunList({
  runs,
  selectedRunId,
  onSelectRun,
  onDeleteRun,
  isDeletingRunId,
}: RunListProps): React.JSX.Element {
  if (runs.length === 0) {
    return (
      <div className="py-12 flex flex-col items-center gap-3 text-sm text-muted-foreground">
        <span>No runs yet.</span>
      </div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Run ID</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Stage</TableHead>
          <TableHead>Duration</TableHead>
          <TableHead>Config Version</TableHead>
          <TableHead className="w-10" />
        </TableRow>
      </TableHeader>
      <TableBody>
        {runs.map((run) => (
          <TableRow
            key={run.id}
            onClick={() => onSelectRun(run.id)}
            className={`group cursor-pointer ${selectedRunId === run.id ? "bg-accent" : "hover:bg-muted/50"}`}
          >
            <TableCell className="font-mono text-xs">{run.id.slice(0, 8)}</TableCell>
            <TableCell>
              <Badge variant={statusVariant(run.status)}>{run.status}</Badge>
            </TableCell>
            <TableCell className="text-sm text-muted-foreground">
              {run.currentStage ?? "—"}
            </TableCell>
            <TableCell className="text-sm text-muted-foreground">
              {formatDuration(run.startedAt, run.completedAt)}
            </TableCell>
            <TableCell className="font-mono text-xs text-muted-foreground">
              {run.configVersionId.slice(0, 8)}
            </TableCell>
            <TableCell className="w-10 text-right">
              {DELETABLE_STATUSES.has(run.status) && (
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-destructive"
                  disabled={isDeletingRunId === run.id}
                  onClick={(e) => {
                    e.stopPropagation();
                    onDeleteRun(run.id);
                  }}
                  aria-label="Delete run"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              )}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
