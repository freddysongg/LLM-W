import * as React from "react";
import { cn } from "@/lib/utils";

export interface RunRowProps {
  readonly children: React.ReactNode;
  readonly selected?: boolean;
  readonly isHeader?: boolean;
  readonly onClick?: () => void;
  readonly className?: string;
}

export function RunRow({
  children,
  selected = false,
  isHeader = false,
  onClick,
  className,
}: RunRowProps): React.JSX.Element {
  const handleKeyDown = (event: React.KeyboardEvent<HTMLDivElement>): void => {
    if (!onClick) return;
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onClick();
    }
  };

  return (
    <div
      role={onClick ? "button" : "row"}
      tabIndex={onClick ? 0 : undefined}
      onClick={onClick}
      onKeyDown={onClick ? handleKeyDown : undefined}
      aria-selected={onClick ? selected : undefined}
      className={cn(
        "group relative grid items-center gap-3 border-b border-hairline px-3 py-2",
        "transition-colors duration-[var(--dur-1)]",
        onClick && "cursor-pointer hover:bg-surface-2",
        "last:border-b-0",
        selected && "bg-surface-2",
        isHeader &&
          "cursor-default bg-surface-2 font-mono text-[10px] uppercase tracking-[0.1em] text-ink-3",
        "focus-visible:outline-none focus-visible:[box-shadow:var(--focus-ring)]",
        className,
      )}
    >
      {selected ? (
        <span
          aria-hidden="true"
          className="absolute left-0 top-0 bottom-0 w-0.5 bg-ink-1 animate-fade-in"
        />
      ) : null}
      {children}
    </div>
  );
}

export interface RunRowCellProps {
  readonly children: React.ReactNode;
  readonly className?: string;
  readonly align?: "start" | "end" | "center";
}

export function RunRowCell({
  children,
  className,
  align = "start",
}: RunRowCellProps): React.JSX.Element {
  return (
    <div
      role="cell"
      className={cn(
        "font-mono text-[11px] text-ink-2",
        align === "end" && "text-right",
        align === "center" && "text-center",
        className,
      )}
    >
      {children}
    </div>
  );
}

export interface RunRowActionsProps {
  readonly children: React.ReactNode;
  readonly className?: string;
}

export function RunRowActions({ children, className }: RunRowActionsProps): React.JSX.Element {
  return (
    <div
      className={cn(
        "flex items-center justify-end gap-1",
        "opacity-0 transition-opacity duration-[var(--dur-1)] group-hover:opacity-100 focus-within:opacity-100",
        className,
      )}
    >
      {children}
    </div>
  );
}
