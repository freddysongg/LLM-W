import * as React from "react";
import { cn } from "@/lib/utils";

export type ArchStageKind = "embed" | "stack" | "norm" | "head";

const ACCENT_CLASS: Record<ArchStageKind, string> = {
  embed: "before:bg-[color:var(--iris-3)]",
  stack: "before:bg-[color:var(--iris-4)]",
  norm: "before:bg-[color:var(--warn)] before:opacity-70",
  head: "before:bg-[color:var(--success)] before:opacity-70",
};

interface ArchStageProps {
  readonly label: string;
  readonly sub: string;
  readonly params: string;
  readonly kind: ArchStageKind;
  readonly isSelected: boolean;
  readonly onSelect: () => void;
  readonly children?: React.ReactNode;
}

export function ArchStage({
  label,
  sub,
  params,
  kind,
  isSelected,
  onSelect,
  children,
}: ArchStageProps): React.JSX.Element {
  const isStack = kind === "stack";
  return (
    <button
      type="button"
      aria-pressed={isSelected}
      onClick={onSelect}
      className={cn(
        "relative flex min-w-0 flex-1 flex-col gap-1 rounded-md border p-3 text-left",
        "transition-[border-color,background-color,transform,box-shadow] duration-[var(--dur-2)]",
        "hover:-translate-y-px hover:border-hairline-strong hover:bg-surface-2 hover:shadow-token-sm",
        "focus-visible:outline-none focus-visible:[box-shadow:var(--focus-ring)]",
        "before:absolute before:left-0 before:top-2.5 before:bottom-2.5 before:w-0.5 before:rounded-[2px]",
        ACCENT_CLASS[kind],
        isStack
          ? "flex-[1.3] bg-[linear-gradient(180deg,var(--surface)_0%,color-mix(in_oklch,var(--iris-1)_25%,var(--surface))_100%)]"
          : "bg-surface",
        isSelected
          ? "border-ink-1 shadow-[0_0_0_2px_color-mix(in_oklch,var(--ink-1)_12%,transparent)]"
          : "border-hairline",
      )}
    >
      <div className="font-mono text-[12px] font-semibold leading-tight tracking-[-0.01em] text-ink-1">
        {label}
      </div>
      <div className="font-mono text-[10px] text-ink-3">{sub}</div>
      <div className="absolute right-2.5 top-2 font-mono text-[9.5px] text-ink-4">{params}</div>
      {children}
    </button>
  );
}
