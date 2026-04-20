import * as React from "react";
import { cn } from "@/lib/utils";

interface BenchmarkBarProps {
  readonly label: string;
  readonly percent: number;
  readonly tone: "base" | "ft";
}

function BenchmarkBar({ label, percent, tone }: BenchmarkBarProps): React.JSX.Element {
  const clamped = Math.max(0, Math.min(100, percent));
  const fillBackground =
    tone === "ft" ? "linear-gradient(90deg, var(--iris-2), var(--iris-4))" : "var(--ink-3)";
  return (
    <div className="grid items-center gap-2" style={{ gridTemplateColumns: "30px 1fr 48px" }}>
      <span
        className={cn(
          "font-mono text-[10px]",
          tone === "ft" ? "text-[color:var(--iris-4)]" : "text-ink-3",
        )}
      >
        {label}
      </span>
      <div
        className="h-2 overflow-hidden rounded-full"
        style={{ background: "var(--surface-3)" }}
        aria-hidden="true"
      >
        <div
          className="h-full rounded-full transition-[width] duration-[260ms] ease-[cubic-bezier(0.22,1,0.36,1)]"
          style={{ width: `${clamped}%`, background: fillBackground }}
        />
      </div>
      <span className="text-right font-mono text-[11px] text-ink-2">{clamped.toFixed(1)}</span>
    </div>
  );
}

export interface BenchmarkRowProps {
  readonly name: string;
  readonly basePercent: number;
  readonly ftPercent: number;
  readonly deltaPercent: number;
}

export function BenchmarkRow({
  name,
  basePercent,
  ftPercent,
  deltaPercent,
}: BenchmarkRowProps): React.JSX.Element {
  const isPositive = deltaPercent >= 0;
  return (
    <div
      className="grid items-center gap-4 border-t border-hairline px-4 py-3 first:border-t-0"
      style={{ gridTemplateColumns: "1.2fr 1.6fr 1.6fr 60px" }}
    >
      <div className="text-[13px] font-medium text-ink-1">{name}</div>
      <BenchmarkBar label="base" percent={basePercent} tone="base" />
      <BenchmarkBar label="ft" percent={ftPercent} tone="ft" />
      <div
        className={cn(
          "text-right font-mono text-[12px] font-semibold",
          isPositive ? "text-[color:var(--success)]" : "text-[color:var(--danger)]",
        )}
      >
        {isPositive ? "+" : ""}
        {deltaPercent.toFixed(1)}
      </div>
    </div>
  );
}
