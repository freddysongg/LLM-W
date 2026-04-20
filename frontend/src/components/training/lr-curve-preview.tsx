import * as React from "react";
import type { SchedulerType } from "@/types/config";

interface LRCurvePreviewProps {
  readonly schedule: SchedulerType;
  readonly warmupSteps: number;
  readonly totalSteps: number;
  readonly className?: string;
}

const SAMPLE_COUNT = 160;
const VIEW_WIDTH = 480;
const VIEW_HEIGHT = 200;
const PADDING_X = 20;
const TOP_Y = 40;
const BOTTOM_Y = 180;

function scheduleValue({
  schedule,
  progress,
}: {
  readonly schedule: SchedulerType;
  readonly progress: number;
}): number {
  switch (schedule) {
    case "cosine":
    case "cosine_with_restarts":
      return 0.5 * (1 + Math.cos(progress * Math.PI));
    case "linear":
      return 1 - progress;
    case "constant":
    case "constant_with_warmup":
      return 1;
    default: {
      const _exhaustive: never = schedule;
      return _exhaustive;
    }
  }
}

function buildPath({
  schedule,
  warmupSteps,
  totalSteps,
}: {
  readonly schedule: SchedulerType;
  readonly warmupSteps: number;
  readonly totalSteps: number;
}): {
  readonly line: string;
  readonly area: string;
  readonly warmupPixelX: number;
} {
  const effectiveTotal = Math.max(totalSteps, 1);
  const effectiveWarmup = Math.max(0, Math.min(warmupSteps, effectiveTotal));
  const plotWidth = VIEW_WIDTH - PADDING_X * 2;
  const plotHeight = BOTTOM_Y - TOP_Y;
  const coords: Array<[number, number]> = [];

  for (let index = 0; index < SAMPLE_COUNT; index += 1) {
    const stepRatio = index / (SAMPLE_COUNT - 1);
    const step = stepRatio * effectiveTotal;
    let intensity: number;
    if (step < effectiveWarmup) {
      intensity = effectiveWarmup === 0 ? 1 : step / effectiveWarmup;
    } else {
      const postWarmupProgress =
        (step - effectiveWarmup) / Math.max(1, effectiveTotal - effectiveWarmup);
      intensity = scheduleValue({ schedule, progress: postWarmupProgress });
    }
    const clampedIntensity = Math.max(0, Math.min(1, intensity));
    const pixelX = PADDING_X + stepRatio * plotWidth;
    const pixelY = BOTTOM_Y - clampedIntensity * plotHeight;
    coords.push([pixelX, pixelY]);
  }

  const line = coords
    .map((coord, index) => `${index === 0 ? "M" : "L"}${coord[0]},${coord[1]}`)
    .join(" ");
  const firstX = coords[0][0];
  const lastX = coords[coords.length - 1][0];
  const area = `${line} L${lastX},${BOTTOM_Y} L${firstX},${BOTTOM_Y} Z`;
  const warmupPixelX = PADDING_X + (effectiveWarmup / effectiveTotal) * plotWidth;

  return { line, area, warmupPixelX };
}

export function LRCurvePreview({
  schedule,
  warmupSteps,
  totalSteps,
  className,
}: LRCurvePreviewProps): React.JSX.Element {
  const gradientId = React.useId();
  const { line, area, warmupPixelX } = React.useMemo(
    () => buildPath({ schedule, warmupSteps, totalSteps }),
    [schedule, warmupSteps, totalSteps],
  );

  return (
    <svg
      className={className}
      viewBox={`0 0 ${VIEW_WIDTH} ${VIEW_HEIGHT}`}
      role="img"
      aria-label="Learning rate schedule preview"
      style={{ width: "100%", display: "block" }}
    >
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--iris-3)" stopOpacity="0.3" />
          <stop offset="100%" stopColor="var(--iris-3)" stopOpacity="0" />
        </linearGradient>
      </defs>
      {[0.25, 0.5, 0.75, 1].map((fraction) => {
        const gridY = BOTTOM_Y - fraction * (BOTTOM_Y - TOP_Y);
        return (
          <line
            key={fraction}
            x1={PADDING_X}
            x2={VIEW_WIDTH - PADDING_X}
            y1={gridY}
            y2={gridY}
            stroke="var(--hairline)"
            strokeDasharray="2 3"
          />
        );
      })}
      <path d={area} fill={`url(#${gradientId})`} />
      <path d={line} fill="none" stroke="var(--iris-3)" strokeWidth={1.6} />
      {warmupSteps > 0 ? (
        <>
          <line
            x1={warmupPixelX}
            x2={warmupPixelX}
            y1={TOP_Y}
            y2={BOTTOM_Y}
            stroke="var(--ink-4)"
            strokeDasharray="3 4"
          />
          <text
            x={warmupPixelX + 4}
            y={TOP_Y + 8}
            fontFamily="var(--font-mono)"
            fontSize={10}
            fill="var(--ink-3)"
          >
            warmup
          </text>
        </>
      ) : null}
    </svg>
  );
}
