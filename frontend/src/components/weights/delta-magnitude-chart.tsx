import * as React from "react";
import type { WeightDelta } from "@/types/model";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

interface DeltaMagnitudeChartProps {
  readonly deltas: ReadonlyArray<WeightDelta>;
}

interface ChartEntry {
  readonly label: string;
  readonly magnitude: number;
}

function truncateLayerName(name: string): string {
  const parts = name.split(".");
  return parts.length > 3 ? `…${parts.slice(-2).join(".")}` : name;
}

export function DeltaMagnitudeChart({ deltas }: DeltaMagnitudeChartProps): React.JSX.Element {
  if (deltas.length === 0) {
    return (
      <div className="py-8 text-center text-sm text-muted-foreground">
        No delta data. Capture two activation snapshots to compare.
      </div>
    );
  }

  const sorted = [...deltas].sort((a, b) => b.deltaMagnitude - a.deltaMagnitude);
  const maxMag = sorted[0]?.deltaMagnitude ?? 1;

  const chartData: ReadonlyArray<ChartEntry> = sorted.map(({ layerName, deltaMagnitude }) => ({
    label: truncateLayerName(layerName),
    magnitude: deltaMagnitude,
  }));

  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={chartData as ChartEntry[]}
          layout="vertical"
          margin={{ top: 0, right: 12, left: 8, bottom: 0 }}
        >
          <CartesianGrid strokeDasharray="3 3" horizontal={false} />
          <XAxis
            type="number"
            domain={[0, maxMag * 1.05]}
            tickFormatter={(v: number) => v.toFixed(3)}
            tick={{ fontSize: 10 }}
          />
          <YAxis
            type="category"
            dataKey="label"
            width={120}
            tick={{ fontSize: 10, fontFamily: "monospace" }}
          />
          <Tooltip
            formatter={(value: number) => [value.toFixed(5), "Δ magnitude"]}
            labelFormatter={(label) => `Layer: ${label}`}
          />
          <Bar dataKey="magnitude" radius={[0, 2, 2, 0]}>
            {(chartData as ChartEntry[]).map(({ magnitude }, idx) => (
              <Cell
                key={idx}
                fill={`hsl(${Math.round(220 - (magnitude / maxMag) * 120)}, 80%, 55%)`}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
