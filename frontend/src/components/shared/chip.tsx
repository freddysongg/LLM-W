import * as React from "react";
import { cn } from "@/lib/utils";

export interface ChipProps {
  readonly label: string;
  readonly isOn: boolean;
  readonly onToggle: () => void;
  readonly className?: string;
}

export function Chip({ label, isOn, onToggle, className }: ChipProps): React.JSX.Element {
  return (
    <button
      type="button"
      aria-pressed={isOn}
      onClick={onToggle}
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-[5px]",
        "font-mono text-[11px] leading-none",
        "transition-[background-color,border-color,color] duration-[var(--dur-1)]",
        "focus-visible:outline-none focus-visible:[box-shadow:var(--focus-ring)]",
        isOn
          ? "border-[color:var(--iris-3)] bg-[color-mix(in_oklch,var(--iris-1)_30%,var(--surface))] text-ink-1"
          : "border-hairline bg-surface-2 text-ink-2 hover:border-hairline-strong",
        className,
      )}
    >
      {label}
    </button>
  );
}
