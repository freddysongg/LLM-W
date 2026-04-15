import * as React from "react";
import type { EvalRun, EvalRunStatus } from "@/types/eval";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";

interface EvalRunListProps {
  readonly evalRuns: ReadonlyArray<EvalRun>;
  readonly selectedEvalRunId: string | null;
  readonly onSelectEvalRun: (evalRunId: string) => void;
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

function formatPassRate(passRate: number | null): string {
  if (passRate === null) return "—";
  return `${Math.round(passRate * 100)}%`;
}

function formatTimestamp(timestamp: string): string {
  return new Date(timestamp).toLocaleString();
}

export function EvalRunList({
  evalRuns,
  selectedEvalRunId,
  onSelectEvalRun,
}: EvalRunListProps): React.JSX.Element {
  if (evalRuns.length === 0) {
    return (
      <div className="py-12 flex flex-col items-center gap-3 text-sm text-muted-foreground">
        <span>No eval runs yet. Trigger one above to get started.</span>
      </div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Eval run ID</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Pass rate</TableHead>
          <TableHead>Cost</TableHead>
          <TableHead>Started</TableHead>
          <TableHead>Training run</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {evalRuns.map((evalRun) => {
          const { id, status, passRate, totalCostUsd, startedAt, trainingRunId } = evalRun;
          return (
            <TableRow
              key={id}
              onClick={() => onSelectEvalRun(id)}
              className={`cursor-pointer ${selectedEvalRunId === id ? "bg-accent" : "hover:bg-muted/50"}`}
            >
              <TableCell className="font-mono text-xs">{id.slice(0, 8)}</TableCell>
              <TableCell>
                <Badge variant={statusVariant(status)}>{status}</Badge>
              </TableCell>
              <TableCell className="text-sm">{formatPassRate(passRate)}</TableCell>
              <TableCell className="text-sm text-muted-foreground">
                {formatUsd(totalCostUsd)}
              </TableCell>
              <TableCell className="text-xs text-muted-foreground">
                {formatTimestamp(startedAt)}
              </TableCell>
              <TableCell className="font-mono text-xs text-muted-foreground">
                {trainingRunId ? trainingRunId.slice(0, 8) : "standalone"}
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
