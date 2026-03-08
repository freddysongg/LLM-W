import * as React from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { MetricPoint } from "@/types/run";

const CHART_COLORS = [
  "hsl(var(--primary))",
  "#22c55e",
  "#f97316",
  "#8b5cf6",
  "#ec4899",
  "#06b6d4",
  "#eab308",
  "#ef4444",
];

interface MetricOverlayChartProps {
  readonly runIds: ReadonlyArray<string>;
  readonly runMetrics: Record<string, ReadonlyArray<MetricPoint>>;
  readonly metricName: string;
  readonly title: string;
}

interface OverlayDataPoint {
  readonly step: number;
  readonly [runId: string]: number;
}

function buildOverlayData(
  runIds: ReadonlyArray<string>,
  runMetrics: Record<string, ReadonlyArray<MetricPoint>>,
  metricName: string,
): ReadonlyArray<OverlayDataPoint> {
  const stepValues = new Map<number, Record<string, number>>();

  for (const runId of runIds) {
    const points = runMetrics[runId] ?? [];
    for (const point of points) {
      if (point.metricName !== metricName) continue;
      const existing = stepValues.get(point.step) ?? {};
      stepValues.set(point.step, { ...existing, [runId]: point.metricValue });
    }
  }

  return Array.from(stepValues.entries())
    .sort(([a], [b]) => a - b)
    .map(([step, values]) => ({ step, ...values }));
}

export function MetricOverlayChart({
  runIds,
  runMetrics,
  metricName,
  title,
}: MetricOverlayChartProps): React.JSX.Element {
  const data = buildOverlayData(runIds, runMetrics, metricName);

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {data.length === 0 ? (
          <div className="h-40 flex items-center justify-center text-xs text-muted-foreground">
            No data available
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={data as OverlayDataPoint[]}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis
                dataKey="step"
                tick={{ fontSize: 10 }}
                tickLine={false}
                axisLine={false}
                label={{ value: "Step", position: "insideBottom", offset: -2, fontSize: 10 }}
              />
              <YAxis tick={{ fontSize: 10 }} tickLine={false} axisLine={false} width={55} />
              <Tooltip
                contentStyle={{
                  fontSize: 11,
                  background: "hsl(var(--popover))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: 6,
                }}
                formatter={(value: number, name: string) => [
                  String(Math.round(value * 10000) / 10000),
                  name.slice(0, 8),
                ]}
              />
              <Legend
                formatter={(value: string) => (
                  <span className="text-xs font-mono">{value.slice(0, 8)}</span>
                )}
              />
              {runIds.map((runId, i) => (
                <Line
                  key={runId}
                  type="monotone"
                  dataKey={runId}
                  stroke={CHART_COLORS[i % CHART_COLORS.length]}
                  dot={false}
                  strokeWidth={1.5}
                  isAnimationActive={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}
