import * as React from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import type { RunMetricSummary } from "@/types/run";

interface MetricComparisonTableProps {
  readonly runIds: ReadonlyArray<string>;
  readonly metricComparison: Record<string, Record<string, RunMetricSummary>>;
}

type TrendVariant = "default" | "secondary" | "destructive" | "outline";

function trendVariant(trend: string): TrendVariant {
  if (trend === "decreasing") return "secondary";
  if (trend === "increasing") return "default";
  return "outline";
}

function formatNumber(value: number): string {
  if (Math.abs(value) < 0.001) return value.toExponential(3);
  return String(Math.round(value * 10000) / 10000);
}

export function MetricComparisonTable({
  runIds,
  metricComparison,
}: MetricComparisonTableProps): React.JSX.Element {
  const metricNames = Object.keys(metricComparison);

  if (metricNames.length === 0) {
    return (
      <div className="flex items-center justify-center h-24 text-sm text-muted-foreground">
        No metric data recorded for the selected runs.
      </div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-44">Metric</TableHead>
          {runIds.map((runId) => (
            <TableHead key={runId} className="font-mono text-xs min-w-40">
              {runId.slice(0, 8)}
            </TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {metricNames.map((metric) => (
          <TableRow key={metric}>
            <TableCell className="font-mono text-xs text-muted-foreground">{metric}</TableCell>
            {runIds.map((runId) => {
              const summary = metricComparison[metric]?.[runId];
              if (!summary) {
                return (
                  <TableCell key={runId} className="text-muted-foreground text-xs">
                    —
                  </TableCell>
                );
              }
              return (
                <TableCell key={runId}>
                  <div className="flex flex-col gap-0.5">
                    <span className="text-xs font-mono">final: {formatNumber(summary.final)}</span>
                    <span className="text-xs font-mono text-muted-foreground">
                      min: {formatNumber(summary.min)}
                    </span>
                    <Badge variant={trendVariant(summary.trend)} className="w-fit text-xs mt-0.5">
                      {summary.trend}
                    </Badge>
                  </div>
                </TableCell>
              );
            })}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
