import * as React from "react";
import type { MetricName, MetricPoint } from "@/types/run";
import { ChartBox } from "@/components/shared/chart-box";
import type { ChartSeries } from "@/components/shared/chart-box";

interface LiveMetricsChartsProps {
  readonly metricPoints: ReadonlyArray<MetricPoint>;
}

interface ChartSpec {
  readonly metric: MetricName;
  readonly title: string;
  readonly color: string;
}

const CHART_SPECS: ReadonlyArray<ChartSpec> = [
  { metric: "train_loss", title: "train/loss", color: "oklch(0.58 0.18 260)" },
  { metric: "eval_loss", title: "eval/loss", color: "oklch(0.62 0.14 155)" },
  { metric: "grad_norm", title: "grad_norm", color: "oklch(0.80 0.14 260)" },
  { metric: "learning_rate", title: "lr_schedule", color: "oklch(0.82 0.13 310)" },
];

function buildSeries({
  metric,
  title,
  color,
  points,
}: ChartSpec & { readonly points: ReadonlyArray<MetricPoint> }): ChartSeries {
  const filtered = points
    .filter((point) => point.metricName === metric)
    .sort((left, right) => left.step - right.step)
    .map(({ step, metricValue }) => ({ x: step, y: metricValue }));
  return {
    key: metric,
    label: title,
    color,
    data: filtered,
  };
}

export function LiveMetricsCharts({ metricPoints }: LiveMetricsChartsProps): React.JSX.Element {
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      {CHART_SPECS.map((spec) => (
        <ChartBox
          key={spec.metric}
          title={spec.title}
          series={[buildSeries({ ...spec, points: metricPoints })]}
          height={200}
        />
      ))}
    </div>
  );
}
