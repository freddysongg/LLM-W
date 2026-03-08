import * as React from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
} from "recharts";
import type { TokenStats } from "@/types/dataset";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface TokenStatsChartProps {
  readonly tokenStats: TokenStats;
  readonly maxSeqLength?: number | null;
}

interface PercentileBar {
  readonly label: string;
  readonly tokens: number;
}

function buildPercentileSeries(stats: TokenStats): ReadonlyArray<PercentileBar> {
  return [
    { label: "min", tokens: stats.min },
    { label: "mean", tokens: Math.round(stats.mean) },
    { label: "median", tokens: Math.round(stats.median) },
    { label: "p95", tokens: Math.round(stats.p95) },
    { label: "p99", tokens: Math.round(stats.p99) },
    { label: "max", tokens: stats.max },
  ];
}

export function TokenStatsChart({
  tokenStats,
  maxSeqLength,
}: TokenStatsChartProps): React.JSX.Element {
  const data = buildPercentileSeries(tokenStats);

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">Token Length Distribution</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={160}>
          <BarChart
            data={data as PercentileBar[]}
            margin={{ top: 4, right: 8, bottom: 0, left: 0 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
            <XAxis dataKey="label" tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
            <YAxis
              tick={{ fontSize: 10 }}
              tickLine={false}
              axisLine={false}
              width={45}
              tickFormatter={(v: number) => v.toLocaleString()}
            />
            <Tooltip
              contentStyle={{
                fontSize: 11,
                background: "hsl(var(--popover))",
                border: "1px solid hsl(var(--border))",
                borderRadius: 6,
              }}
              formatter={(v: number) => [v.toLocaleString(), "tokens"]}
            />
            <Bar dataKey="tokens" fill="hsl(var(--primary))" radius={[3, 3, 0, 0]} />
            {maxSeqLength != null && (
              <ReferenceLine
                y={maxSeqLength}
                stroke="hsl(var(--destructive))"
                strokeDasharray="4 2"
                label={{
                  value: `max_seq: ${maxSeqLength}`,
                  position: "insideTopRight",
                  fontSize: 10,
                }}
              />
            )}
          </BarChart>
        </ResponsiveContainer>
        <div className="mt-2 grid grid-cols-3 gap-2 text-xs text-muted-foreground">
          <span>Min: {tokenStats.min.toLocaleString()}</span>
          <span>Mean: {Math.round(tokenStats.mean).toLocaleString()}</span>
          <span>Median: {Math.round(tokenStats.median).toLocaleString()}</span>
          <span>p95: {Math.round(tokenStats.p95).toLocaleString()}</span>
          <span>p99: {Math.round(tokenStats.p99).toLocaleString()}</span>
          <span>Max: {tokenStats.max.toLocaleString()}</span>
        </div>
      </CardContent>
    </Card>
  );
}
