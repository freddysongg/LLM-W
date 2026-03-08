import * as React from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { MetricPoint } from "@/types/run";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface LiveMetricsChartsProps {
  readonly metricPoints: ReadonlyArray<MetricPoint>;
}

interface ChartDataPoint {
  readonly step: number;
  readonly value: number;
}

function buildSeries(
  points: ReadonlyArray<MetricPoint>,
  metricName: string,
): ReadonlyArray<ChartDataPoint> {
  return points
    .filter((p) => p.metricName === metricName)
    .map(({ step, metricValue }) => ({ step, value: metricValue }));
}

interface MetricChartProps {
  readonly title: string;
  readonly data: ReadonlyArray<ChartDataPoint>;
  readonly color: string;
  readonly yFormatter?: (value: number) => string;
}

function MetricChart({ title, data, color, yFormatter }: MetricChartProps): React.JSX.Element {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-xs text-muted-foreground font-normal">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {data.length === 0 ? (
          <div className="h-24 flex items-center justify-center text-xs text-muted-foreground">
            Waiting for data…
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={96}>
            <LineChart data={data as ChartDataPoint[]}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis dataKey="step" tick={{ fontSize: 10 }} tickLine={false} axisLine={false} />
              <YAxis
                tick={{ fontSize: 10 }}
                tickLine={false}
                axisLine={false}
                tickFormatter={yFormatter}
                width={50}
              />
              <Tooltip
                contentStyle={{
                  fontSize: 11,
                  background: "hsl(var(--popover))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: 6,
                }}
                formatter={(val: number) =>
                  yFormatter ? yFormatter(val) : String(Math.round(val * 10000) / 10000)
                }
              />
              <Line
                type="monotone"
                dataKey="value"
                stroke={color}
                dot={false}
                strokeWidth={1.5}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}

export function LiveMetricsCharts({ metricPoints }: LiveMetricsChartsProps): React.JSX.Element {
  const trainLoss = buildSeries(metricPoints, "train_loss");
  const learningRate = buildSeries(metricPoints, "learning_rate");
  const gradNorm = buildSeries(metricPoints, "grad_norm");
  const throughput = buildSeries(metricPoints, "tokens_per_second");
  const memory = buildSeries(metricPoints, "gpu_memory_used_mb");

  const scientificFormatter = (val: number): string => val.toExponential(2);
  const mbFormatter = (val: number): string => `${Math.round(val)}MB`;

  return (
    <div className="grid grid-cols-2 gap-3">
      <MetricChart title="Training Loss" data={trainLoss} color="hsl(var(--primary))" />
      <MetricChart
        title="Learning Rate"
        data={learningRate}
        color="#22c55e"
        yFormatter={scientificFormatter}
      />
      <MetricChart title="Gradient Norm" data={gradNorm} color="#f97316" />
      <MetricChart title="Throughput (tok/s)" data={throughput} color="#8b5cf6" />
      <MetricChart title="GPU Memory" data={memory} color="#ec4899" yFormatter={mbFormatter} />
    </div>
  );
}
