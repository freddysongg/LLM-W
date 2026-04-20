import * as React from "react";
import { ChartBoxOverlay } from "@/components/shared/chart-box";
import type { ChartPoint, ChartSeries } from "@/components/shared/chart-box";
import { colorForRunId } from "@/lib/run-color-palette";
import type { MetricPoint } from "@/types/run";

interface MetricOverlayChartProps {
  readonly runIds: ReadonlyArray<string>;
  readonly runMetrics: Record<string, ReadonlyArray<MetricPoint>>;
  readonly metricName: string;
  readonly title: string;
}

function buildSeries({
  runIds,
  runMetrics,
  metricName,
}: {
  readonly runIds: ReadonlyArray<string>;
  readonly runMetrics: Record<string, ReadonlyArray<MetricPoint>>;
  readonly metricName: string;
}): ReadonlyArray<ChartSeries> {
  return runIds.map((runId) => {
    const points = runMetrics[runId] ?? [];
    const seriesPoints: ReadonlyArray<ChartPoint> = points
      .filter((point) => point.metricName === metricName)
      .map((point) => ({ x: point.step, y: point.metricValue }));
    return {
      key: runId,
      label: runId.slice(0, 8),
      data: seriesPoints,
      color: colorForRunId(runId),
    };
  });
}

export function MetricOverlayChart({
  runIds,
  runMetrics,
  metricName,
  title,
}: MetricOverlayChartProps): React.JSX.Element {
  const series = React.useMemo(
    () => buildSeries({ runIds, runMetrics, metricName }),
    [runIds, runMetrics, metricName],
  );
  const hasData = series.some((entry) => entry.data.length > 0);

  if (!hasData) {
    return (
      <div className="rounded-md border border-hairline bg-surface p-4 text-center font-mono text-[11px] text-ink-3">
        No data for {title.toLowerCase()}.
      </div>
    );
  }

  return <ChartBoxOverlay title={title} series={series} height={200} />;
}
