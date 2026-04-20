import * as React from "react";
import type { MetricPoint, Run } from "@/types/run";
import type { MetricDelta } from "@/components/shared/metric-tile";
import { MetricTile } from "@/components/shared/metric-tile";

interface DashboardMetricsRowProps {
  readonly runs: ReadonlyArray<Run>;
  readonly liveMetrics: ReadonlyArray<MetricPoint>;
  readonly historicalMetrics: ReadonlyArray<MetricPoint>;
}

const SPARK_WINDOW = 20;
const FLAT_DELTA_THRESHOLD_PCT = 0.5;

type TileMetric = "train_loss" | "eval_loss" | "tokens_per_second";

interface TileConfig {
  readonly metric: TileMetric;
  readonly label: string;
  readonly decimals: number;
  readonly sparkColor: string;
  readonly suffix?: string;
  readonly sentimentInverted?: boolean;
}

const TILE_CONFIGS: ReadonlyArray<TileConfig> = [
  {
    metric: "train_loss",
    label: "Train loss",
    decimals: 4,
    sparkColor: "var(--iris-3)",
    sentimentInverted: true,
  },
  {
    metric: "eval_loss",
    label: "Eval loss",
    decimals: 4,
    sparkColor: "var(--success)",
    sentimentInverted: true,
  },
  {
    metric: "tokens_per_second",
    label: "Tokens / sec",
    decimals: 0,
    sparkColor: "var(--iris-4)",
  },
];

function collectSeries({
  metric,
  liveMetrics,
  historicalMetrics,
}: {
  readonly metric: TileMetric;
  readonly liveMetrics: ReadonlyArray<MetricPoint>;
  readonly historicalMetrics: ReadonlyArray<MetricPoint>;
}): ReadonlyArray<number> {
  const merged = [...historicalMetrics, ...liveMetrics];
  const filtered = merged.filter((point) => point.metricName === metric);
  filtered.sort((left, right) => left.step - right.step);
  return filtered.slice(-SPARK_WINDOW).map(({ metricValue }) => metricValue);
}

function computeDelta({
  window,
  sentimentInverted,
}: {
  readonly window: ReadonlyArray<number>;
  readonly sentimentInverted: boolean;
}): MetricDelta | undefined {
  if (window.length < 2) return undefined;
  const first = window[0];
  const last = window[window.length - 1];
  if (!Number.isFinite(first) || !Number.isFinite(last) || first === 0) return undefined;
  const changePercent = ((last - first) / Math.abs(first)) * 100;
  if (Math.abs(changePercent) < FLAT_DELTA_THRESHOLD_PCT) {
    return { direction: "flat", percent: 0, sentimentInverted };
  }
  return {
    direction: changePercent > 0 ? "up" : "down",
    percent: Math.round(Math.abs(changePercent) * 10) / 10,
    sentimentInverted,
  };
}

function latestValue(window: ReadonlyArray<number>): number {
  if (window.length === 0) return 0;
  return window[window.length - 1];
}

export function DashboardMetricsRow({
  liveMetrics,
  historicalMetrics,
}: DashboardMetricsRowProps): React.JSX.Element {
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
      {TILE_CONFIGS.map(({ metric, label, decimals, sparkColor, suffix, sentimentInverted }) => {
        const series = collectSeries({ metric, liveMetrics, historicalMetrics });
        const delta = computeDelta({
          window: series,
          sentimentInverted: sentimentInverted ?? false,
        });
        return (
          <MetricTile
            key={metric}
            label={label}
            value={latestValue(series)}
            decimals={decimals}
            suffix={suffix}
            spark={series}
            sparkColor={sparkColor}
            delta={delta}
          />
        );
      })}
    </div>
  );
}
