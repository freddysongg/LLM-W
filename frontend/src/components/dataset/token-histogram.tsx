import * as React from "react";
import type { TokenStats } from "@/types/dataset";

interface TokenHistogramProps {
  readonly stats: TokenStats;
}

const BIN_COUNT = 16;
const AXIS_SCALE: ReadonlyArray<number> = [0, 256, 512, 1024, 2048];

function buildSyntheticDensity({
  mean,
  std,
  binCenters,
}: {
  readonly mean: number;
  readonly std: number;
  readonly binCenters: ReadonlyArray<number>;
}): ReadonlyArray<number> {
  const safeStd = std > 0 ? std : Math.max(mean * 0.25, 1);
  return binCenters.map((center) => {
    const z = (center - mean) / safeStd;
    return Math.exp(-0.5 * z * z);
  });
}

export function TokenHistogram({ stats }: TokenHistogramProps): React.JSX.Element {
  const { min, max, mean, median } = stats;

  const binWidth = Math.max(1, (max - min) / BIN_COUNT);
  const binCenters = Array.from({ length: BIN_COUNT }, (_, i) => min + binWidth * (i + 0.5));
  const densities = buildSyntheticDensity({ mean, std: Math.max(median * 0.5, 1), binCenters });
  const peak = Math.max(...densities, 1);

  const chartWidth = 480;
  const chartHeight = 120;
  const baseline = 110;
  const leftPad = 10;
  const plotWidth = chartWidth - leftPad * 2;
  const barSlot = chartWidth / BIN_COUNT;
  const barWidth = barSlot - 8;
  const maxBarHeight = 88;

  const visibleAxisTicks = AXIS_SCALE.filter((tick) => tick >= min && tick <= max);
  const axisRange = Math.max(1, max - min);

  return (
    <svg
      viewBox={`0 0 ${chartWidth} ${chartHeight}`}
      role="img"
      aria-label="Token length distribution"
      className="block w-full"
    >
      {densities.map((density, i) => {
        const barHeight = (density / peak) * maxBarHeight;
        const x = leftPad + i * barSlot;
        const y = baseline - barHeight;
        const mix = 40 + i * 3;
        return (
          <rect
            key={i}
            x={x}
            y={y}
            width={barWidth}
            height={barHeight}
            rx={2}
            fill={`color-mix(in oklch, var(--iris-3) ${mix}%, var(--surface))`}
          />
        );
      })}
      {visibleAxisTicks.map((tick, i) => {
        const xPos = leftPad + ((tick - min) / axisRange) * plotWidth;
        const anchor: "start" | "middle" | "end" =
          i === 0 ? "start" : i === visibleAxisTicks.length - 1 ? "end" : "middle";
        return (
          <text
            key={tick}
            x={xPos}
            y={118}
            fontFamily="var(--font-mono)"
            fontSize={10}
            fill="var(--ink-3)"
            textAnchor={anchor}
          >
            {tick.toLocaleString()}
          </text>
        );
      })}
    </svg>
  );
}
