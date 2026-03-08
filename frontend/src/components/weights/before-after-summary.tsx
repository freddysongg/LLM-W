import * as React from "react";
import type { WeightDelta } from "@/types/model";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

interface BeforeAfterSummaryProps {
  readonly deltas: ReadonlyArray<WeightDelta>;
}

function fmt(value: number): string {
  return value.toFixed(5);
}

export function BeforeAfterSummary({ deltas }: BeforeAfterSummaryProps): React.JSX.Element {
  if (deltas.length === 0) {
    return (
      <div className="py-4 text-sm text-muted-foreground">
        No delta data. Capture two activation snapshots to compare.
      </div>
    );
  }

  const sorted = [...deltas].sort((a, b) => b.deltaMagnitude - a.deltaMagnitude);

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="text-xs">Layer</TableHead>
          <TableHead className="text-xs text-right">Mean (before)</TableHead>
          <TableHead className="text-xs text-right">Mean (after)</TableHead>
          <TableHead className="text-xs text-right">Std (before)</TableHead>
          <TableHead className="text-xs text-right">Std (after)</TableHead>
          <TableHead className="text-xs text-right">Δ magnitude</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {sorted.map(({ layerName, meanBefore, meanAfter, stdBefore, stdAfter, deltaMagnitude }) => (
          <TableRow key={layerName}>
            <TableCell className="font-mono text-xs max-w-40 truncate" title={layerName}>
              {layerName}
            </TableCell>
            <TableCell className="font-mono text-xs text-right">{fmt(meanBefore)}</TableCell>
            <TableCell className="font-mono text-xs text-right">{fmt(meanAfter)}</TableCell>
            <TableCell className="font-mono text-xs text-right">{fmt(stdBefore)}</TableCell>
            <TableCell className="font-mono text-xs text-right">{fmt(stdAfter)}</TableCell>
            <TableCell className="font-mono text-xs text-right font-medium">
              {fmt(deltaMagnitude)}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
