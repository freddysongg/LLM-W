import * as React from "react";
import {
  CartesianGrid,
  Line,
  LineChart as RechartsLineChart,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export interface ChartPoint {
  readonly x: number | string;
  readonly y: number;
}

export interface ChartSeries {
  readonly key: string;
  readonly label: string;
  readonly data: readonly ChartPoint[];
  readonly color: string;
}

export interface ChartBoxProps {
  readonly title?: string;
  readonly series: readonly ChartSeries[];
  readonly height?: number;
  readonly xKey?: string;
  readonly grid?: boolean;
  readonly legend?: boolean;
  readonly className?: string;
}

type MergedPoint = Record<string, number | string>;

function mergeSeries({
  series,
  xKey,
}: {
  readonly series: readonly ChartSeries[];
  readonly xKey: string;
}): readonly MergedPoint[] {
  const byX = new Map<number | string, MergedPoint>();
  for (const { key, data } of series) {
    for (const { x, y } of data) {
      const existing = byX.get(x);
      if (existing) {
        existing[key] = y;
      } else {
        byX.set(x, { [xKey]: x, [key]: y });
      }
    }
  }
  return Array.from(byX.values()).sort((left, right) => {
    const leftX = left[xKey];
    const rightX = right[xKey];
    if (typeof leftX === "number" && typeof rightX === "number") return leftX - rightX;
    return String(leftX).localeCompare(String(rightX));
  });
}

const AXIS_TICK_STYLE: React.CSSProperties = {
  fontFamily: "var(--font-mono)",
  fontSize: 10,
  fill: "var(--ink-3)",
};

const TOOLTIP_CONTENT_STYLE: React.CSSProperties = {
  background: "var(--surface)",
  border: "1px solid var(--hairline)",
  borderRadius: 6,
  fontFamily: "var(--font-mono)",
  fontSize: 11,
  color: "var(--ink-1)",
};

export function ChartBox({
  title,
  series,
  height = 220,
  xKey = "x",
  grid = true,
  legend = false,
  className,
}: ChartBoxProps): React.JSX.Element {
  const mergedData = React.useMemo(() => mergeSeries({ series, xKey }), [series, xKey]);

  return (
    <Card className={cn("p-0", className)}>
      {title ? (
        <CardHeader className="py-3">
          <CardTitle>{title}</CardTitle>
          {legend ? (
            <div className="flex items-center gap-3 font-mono text-[10px] text-ink-3">
              {series.map(({ key, label, color }) => (
                <span key={key} className="inline-flex items-center gap-1.5">
                  <span
                    aria-hidden="true"
                    className="inline-block h-2 w-2 rounded-full"
                    style={{ backgroundColor: color }}
                  />
                  {label}
                </span>
              ))}
            </div>
          ) : null}
        </CardHeader>
      ) : null}
      <CardContent className="p-[18px]">
        <div style={{ height }}>
          <ResponsiveContainer width="100%" height="100%">
            <RechartsLineChart data={mergedData as MergedPoint[]}>
              {grid ? (
                <CartesianGrid stroke="var(--hairline)" strokeDasharray="2 3" vertical={false} />
              ) : null}
              <XAxis
                dataKey={xKey}
                tick={AXIS_TICK_STYLE}
                stroke="var(--hairline)"
                tickLine={false}
              />
              <YAxis tick={AXIS_TICK_STYLE} stroke="var(--hairline)" tickLine={false} />
              <Tooltip
                contentStyle={TOOLTIP_CONTENT_STYLE}
                cursor={{ stroke: "var(--hairline)" }}
              />
              {legend && !title ? <Legend /> : null}
              {series.map(({ key, label, color }) => (
                <Line
                  key={key}
                  type="monotone"
                  dataKey={key}
                  name={label}
                  stroke={color}
                  strokeWidth={1.6}
                  dot={false}
                  isAnimationActive={false}
                />
              ))}
            </RechartsLineChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}

export interface ChartBoxOverlayProps {
  readonly title?: string;
  readonly series: readonly ChartSeries[];
  readonly height?: number;
  readonly xKey?: string;
  readonly className?: string;
}

export function ChartBoxOverlay({
  title,
  series,
  height = 240,
  xKey = "x",
  className,
}: ChartBoxOverlayProps): React.JSX.Element {
  return (
    <ChartBox
      title={title}
      series={series}
      height={height}
      xKey={xKey}
      grid={true}
      legend={true}
      className={className}
    />
  );
}
