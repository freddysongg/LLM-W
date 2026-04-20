import * as React from "react";
import { cn } from "@/lib/utils";

export interface RangePillOption<T extends string> {
  readonly value: T;
  readonly label: string;
  readonly count?: number;
}

export interface RangePillsProps<T extends string> {
  readonly options: readonly RangePillOption<T>[];
  readonly value: T;
  readonly onChange: (next: T) => void;
  readonly className?: string;
  readonly ariaLabel?: string;
}

export function RangePills<T extends string>({
  options,
  value,
  onChange,
  className,
  ariaLabel,
}: RangePillsProps<T>): React.JSX.Element {
  return (
    <div
      role="group"
      aria-label={ariaLabel}
      className={cn(
        "inline-flex items-center gap-0.5 rounded-full border border-hairline bg-surface-2 p-[3px]",
        className,
      )}
    >
      {options.map(({ value: pillValue, label, count }) => {
        const isActive = value === pillValue;
        return (
          <button
            key={pillValue}
            type="button"
            aria-pressed={isActive}
            onClick={() => onChange(pillValue)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1",
              "font-mono text-[10px] uppercase leading-none tracking-[0.08em]",
              "transition-colors duration-[var(--dur-1)]",
              isActive
                ? "bg-ink-1 text-[color:var(--surface)]"
                : "text-ink-2 hover:bg-surface-3 hover:text-ink-1",
            )}
          >
            <span>{label}</span>
            {count !== undefined ? (
              <span
                className={cn(
                  "rounded-full px-1.5 py-px font-mono text-[9px]",
                  isActive ? "bg-[color-mix(in_oklch,var(--ink-1)_75%,transparent)]" : "bg-surface",
                )}
              >
                {count}
              </span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}
