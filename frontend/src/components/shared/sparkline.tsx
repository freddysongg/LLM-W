import * as React from "react";
import { cn } from "@/lib/utils";

export interface SparklineProps {
  readonly data: readonly number[];
  readonly color?: string;
  readonly height?: number;
  readonly strokeWidth?: number;
  readonly fill?: boolean;
  readonly className?: string;
}

interface Point {
  readonly x: number;
  readonly y: number;
}

const VIEW_WIDTH = 120;

function buildPoints({
  data,
  width,
  height,
}: {
  readonly data: readonly number[];
  readonly width: number;
  readonly height: number;
}): readonly Point[] {
  if (data.length === 0) {
    return [
      { x: 0, y: height / 2 },
      { x: width, y: height / 2 },
    ];
  }
  if (data.length === 1) {
    const y = height / 2;
    return [
      { x: 0, y },
      { x: width, y },
    ];
  }
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const stepX = width / (data.length - 1);
  return data.map<Point>((datumY, index) => ({
    x: index * stepX,
    y: height - ((datumY - min) / range) * (height - 4) - 2,
  }));
}

function toPath(points: readonly Point[]): string {
  return points.map((point, index) => `${index === 0 ? "M" : "L"}${point.x},${point.y}`).join(" ");
}

export function Sparkline({
  data,
  color = "currentColor",
  height = 32,
  strokeWidth = 1.5,
  fill = true,
  className,
}: SparklineProps): React.JSX.Element {
  const gradientId = React.useId();
  const points = buildPoints({ data, width: VIEW_WIDTH, height });
  const linePath = toPath(points);
  const areaPath = `${linePath} L${VIEW_WIDTH},${height} L0,${height} Z`;

  return (
    <svg
      className={cn("block w-full", className)}
      style={{ height }}
      viewBox={`0 0 ${VIEW_WIDTH} ${height}`}
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.35" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      {fill ? <path d={areaPath} fill={`url(#${gradientId})`} stroke="none" /> : null}
      <path
        d={linePath}
        fill="none"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinejoin="round"
        strokeLinecap="round"
        strokeDasharray="400"
        className="animate-spark-draw"
      />
    </svg>
  );
}
