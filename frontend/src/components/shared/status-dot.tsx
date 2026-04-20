import * as React from "react";
import { cn } from "@/lib/utils";

export type RunStatus = "running" | "success" | "failed" | "pending" | "paused";

type StatusDotSize = "sm" | "md";

export interface StatusDotProps {
  readonly status: RunStatus;
  readonly size?: StatusDotSize;
  readonly className?: string;
}

const SIZE_PX: Record<StatusDotSize, number> = {
  sm: 8,
  md: 10,
};

const COLOR_VAR: Record<RunStatus, string> = {
  running: "var(--success)",
  success: "var(--success)",
  failed: "var(--danger)",
  pending: "var(--ink-4)",
  paused: "var(--warn)",
};

export function StatusDot({ status, size = "sm", className }: StatusDotProps): React.JSX.Element {
  const dimensionPx = SIZE_PX[size];
  const backgroundColor = COLOR_VAR[status];
  const isRunning = status === "running";

  const style: React.CSSProperties = {
    width: dimensionPx,
    height: dimensionPx,
    backgroundColor,
    boxShadow: isRunning
      ? `0 0 0 3px color-mix(in oklch, ${backgroundColor} 30%, transparent)`
      : undefined,
  };

  return (
    <span
      aria-hidden="true"
      role="presentation"
      style={style}
      className={cn(
        "inline-block shrink-0 rounded-full",
        isRunning && "animate-pulse-dot",
        className,
      )}
    />
  );
}
