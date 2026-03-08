import * as React from "react";
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

interface RecentRunsListProps {
  readonly runs: ReadonlyArray<Run>;
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

export function RecentRunsList({ runs }: RecentRunsListProps): React.JSX.Element {
  if (runs.length === 0) {
    return <div className="py-8 text-center text-sm text-muted-foreground">No runs yet.</div>;
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Run ID</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Duration</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {runs.map((run) => (
          <TableRow key={run.id}>
            <TableCell className="font-mono text-xs">{run.id.slice(0, 8)}</TableCell>
            <TableCell>
              <Badge variant={statusVariant(run.status)}>{run.status}</Badge>
            </TableCell>
            <TableCell className="text-muted-foreground text-sm">
              {formatDuration(run.startedAt, run.completedAt)}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
