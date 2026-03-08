import * as React from "react";
import type { ParameterRow } from "@/types/model";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";

type ParameterFilter = "all" | "trainable" | "frozen";

interface ParameterSummaryTableProps {
  readonly rows: ReadonlyArray<ParameterRow>;
  readonly filter: ParameterFilter;
  readonly onFilterChange: (filter: ParameterFilter) => void;
}

function formatParamCount(params: number): string {
  if (params >= 1e9) return `${(params / 1e9).toFixed(2)}B`;
  if (params >= 1e6) return `${(params / 1e6).toFixed(2)}M`;
  if (params >= 1e3) return `${(params / 1e3).toFixed(1)}K`;
  return String(params);
}

function estimateMemoryMb(params: number, dtype: string | null): string {
  const bytesPerParam = dtype?.includes("16") ? 2 : dtype?.includes("8") ? 1 : 4;
  const mb = (params * bytesPerParam) / (1024 * 1024);
  if (mb < 1) return `${(mb * 1024).toFixed(1)} KB`;
  if (mb >= 1024) return `${(mb / 1024).toFixed(2)} GB`;
  return `${mb.toFixed(2)} MB`;
}

const FILTER_OPTIONS: ReadonlyArray<{ value: ParameterFilter; label: string }> = [
  { value: "all", label: "All" },
  { value: "trainable", label: "Trainable" },
  { value: "frozen", label: "Frozen" },
];

export function ParameterSummaryTable({
  rows,
  filter,
  onFilterChange,
}: ParameterSummaryTableProps): React.JSX.Element {
  const visibleRows = rows.filter((row) => {
    if (filter === "trainable") return row.trainable === true;
    if (filter === "frozen") return row.trainable === false;
    return true;
  });

  const totalParams = visibleRows.reduce((sum, row) => sum + row.params, 0);

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        {FILTER_OPTIONS.map(({ value, label }) => (
          <button
            key={value}
            onClick={() => onFilterChange(value)}
            className={`px-3 py-1 text-xs rounded-md border transition-colors ${
              filter === value
                ? "bg-primary text-primary-foreground border-primary"
                : "bg-background text-muted-foreground border-border hover:bg-muted"
            }`}
          >
            {label}
          </button>
        ))}
        <span className="ml-auto text-xs text-muted-foreground">
          {formatParamCount(totalParams)} params ({visibleRows.length} layers)
        </span>
      </div>

      {visibleRows.length === 0 ? (
        <div className="py-8 text-center text-sm text-muted-foreground">No layers match.</div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="text-xs">Layer</TableHead>
              <TableHead className="text-xs">Type</TableHead>
              <TableHead className="text-xs">Parameters</TableHead>
              <TableHead className="text-xs">dtype</TableHead>
              <TableHead className="text-xs">Memory</TableHead>
              <TableHead className="text-xs">Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {visibleRows.map((row) => (
              <TableRow key={row.path}>
                <TableCell className="font-mono text-xs max-w-48 truncate" title={row.path}>
                  {row.path}
                </TableCell>
                <TableCell className="text-xs text-muted-foreground">{row.type}</TableCell>
                <TableCell className="font-mono text-xs">{formatParamCount(row.params)}</TableCell>
                <TableCell className="font-mono text-xs text-muted-foreground">
                  {row.dtype ?? "—"}
                </TableCell>
                <TableCell className="text-xs text-muted-foreground">
                  {estimateMemoryMb(row.params, row.dtype)}
                </TableCell>
                <TableCell>
                  <Badge variant={row.trainable ? "default" : "secondary"} className="text-xs">
                    {row.trainable === true
                      ? "trainable"
                      : row.trainable === false
                        ? "frozen"
                        : "—"}
                  </Badge>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
