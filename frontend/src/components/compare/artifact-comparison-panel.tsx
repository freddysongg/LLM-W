import * as React from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { RunArtifactSummary } from "@/types/run";

interface ArtifactComparisonPanelProps {
  readonly runIds: ReadonlyArray<string>;
  readonly artifactComparison: Record<string, RunArtifactSummary>;
}

function formatSize(mb: number): string {
  if (mb >= 1024) return `${(mb / 1024).toFixed(1)} GB`;
  return `${mb.toFixed(0)} MB`;
}

export function ArtifactComparisonPanel({
  runIds,
  artifactComparison,
}: ArtifactComparisonPanelProps): React.JSX.Element {
  const hasData = runIds.some((id) => artifactComparison[id] !== undefined);

  if (!hasData) {
    return (
      <div className="flex items-center justify-center h-24 text-sm text-muted-foreground">
        No artifact data available for the selected runs.
      </div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Run</TableHead>
          <TableHead>Checkpoints</TableHead>
          <TableHead>Total Size</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {runIds.map((runId) => {
          const summary = artifactComparison[runId];
          return (
            <TableRow key={runId}>
              <TableCell className="font-mono text-xs">{runId.slice(0, 8)}</TableCell>
              <TableCell className="text-sm">
                {summary != null ? String(summary.checkpoints) : "—"}
              </TableCell>
              <TableCell className="text-sm">
                {summary != null ? formatSize(summary.totalSizeMb) : "—"}
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
