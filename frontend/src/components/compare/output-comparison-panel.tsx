import * as React from "react";
import type { RunMetricSummary } from "@/types/run";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const EVAL_METRIC_LABELS: Readonly<Record<string, string>> = {
  eval_loss: "Eval Loss",
  train_loss: "Train Loss (final)",
  tokens_per_second: "Tokens/sec",
  step_time_ms: "Step Time (ms)",
};

interface OutputComparisonPanelProps {
  readonly runIds: ReadonlyArray<string>;
  readonly metricComparison: Record<string, Record<string, RunMetricSummary>>;
}

export function OutputComparisonPanel({
  runIds,
  metricComparison,
}: OutputComparisonPanelProps): React.JSX.Element {
  const availableMetrics = Object.keys(EVAL_METRIC_LABELS).filter(
    (m) => metricComparison[m] !== undefined,
  );

  if (availableMetrics.length === 0) {
    return (
      <div className="flex items-center justify-center h-24 text-sm text-muted-foreground">
        No evaluation output data available. Runs must include an evaluation stage to appear here.
      </div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Metric</TableHead>
          {runIds.map((runId) => (
            <TableHead key={runId} className="font-mono text-xs">
              {runId.slice(0, 8)}
            </TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {availableMetrics.map((metric) => (
          <TableRow key={metric}>
            <TableCell className="text-sm font-medium">{EVAL_METRIC_LABELS[metric]}</TableCell>
            {runIds.map((runId) => {
              const summary = metricComparison[metric]?.[runId];
              return (
                <TableCell key={runId} className="font-mono text-sm">
                  {summary != null ? summary.final.toFixed(4) : "—"}
                </TableCell>
              );
            })}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
