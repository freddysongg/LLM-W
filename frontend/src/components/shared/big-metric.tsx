import * as React from "react";
import { Counter } from "@/components/shared/counter";
import { cn } from "@/lib/utils";

export interface BigMetricProps {
  readonly value: number | string;
  readonly unit?: string;
  readonly label?: string;
  readonly className?: string;
  readonly decimals?: number;
}

export function BigMetric({
  value,
  unit,
  label,
  className,
  decimals = 0,
}: BigMetricProps): React.JSX.Element {
  const isNumeric = typeof value === "number";

  return (
    <div className={cn("flex flex-col gap-1", className)}>
      {label ? (
        <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-ink-3">{label}</span>
      ) : null}
      <div className="flex items-baseline gap-2 font-mono font-semibold leading-none tracking-[-0.02em] text-ink-1">
        <span className="text-[44px]">
          {isNumeric ? <Counter value={value} decimals={decimals} /> : value}
        </span>
        {unit ? <span className="text-[24px] font-medium text-ink-3">{unit}</span> : null}
      </div>
    </div>
  );
}
