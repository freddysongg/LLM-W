import * as React from "react";
import { Check } from "lucide-react";
import type { RunStatus } from "@/components/shared/status-dot";
import { cn } from "@/lib/utils";

export type TimelineStatus = RunStatus | "done";

export interface TimelineItem {
  readonly id: string;
  readonly title: string;
  readonly sub?: string;
  readonly meta?: string;
  readonly status: TimelineStatus;
  readonly number?: number;
}

export interface TimelineProps {
  readonly items: readonly TimelineItem[];
  readonly onSelect?: (id: string) => void;
  readonly activeId?: string;
  readonly className?: string;
}

interface NodeAppearance {
  readonly className: string;
  readonly style?: React.CSSProperties;
}

function resolveNodeAppearance(status: TimelineStatus): NodeAppearance {
  switch (status) {
    case "done":
    case "success":
      return {
        className: "bg-[color:var(--success)] text-[color:var(--surface)]",
      };
    case "running":
      return {
        className:
          "bg-[color-mix(in_oklch,var(--iris-3)_15%,var(--surface))] text-[color:var(--iris-4)] animate-ring-pulse",
      };
    case "failed":
      return {
        className: "bg-[color:var(--danger)] text-[color:var(--surface)]",
      };
    case "paused":
      return {
        className: "bg-[color:var(--warn)] text-[color:var(--surface)]",
      };
    case "pending":
    default:
      return {
        className: "bg-surface-3 text-ink-3",
      };
  }
}

function renderNodeContent({
  status,
  number,
}: {
  readonly status: TimelineStatus;
  readonly number?: number;
}): React.ReactNode {
  if (status === "done" || status === "success") {
    return <Check className="size-2.5" aria-hidden="true" />;
  }
  if (number !== undefined) return number;
  return null;
}

export function Timeline({
  items,
  onSelect,
  activeId,
  className,
}: TimelineProps): React.JSX.Element {
  return (
    <ol className={cn("flex flex-col gap-0.5", className)}>
      {items.map((item) => {
        const { id, title, sub, meta, status, number } = item;
        const isActive = activeId === id;
        const appearance = resolveNodeAppearance(status);
        const isInteractive = onSelect !== undefined;

        const handleClick = (): void => {
          onSelect?.(id);
        };

        const handleKeyDown = (event: React.KeyboardEvent<HTMLLIElement>): void => {
          if (!isInteractive) return;
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            onSelect(id);
          }
        };

        return (
          <li
            key={id}
            role={isInteractive ? "button" : "listitem"}
            tabIndex={isInteractive ? 0 : undefined}
            onClick={isInteractive ? handleClick : undefined}
            onKeyDown={isInteractive ? handleKeyDown : undefined}
            aria-current={isActive ? "step" : undefined}
            className={cn(
              "grid grid-cols-[28px_1fr_auto] items-center gap-3 rounded-md border border-transparent bg-surface-2 px-3 py-2.5",
              "transition-colors duration-[var(--dur-1)]",
              isInteractive && "cursor-pointer hover:border-hairline hover:bg-surface",
              isActive && "border-hairline-strong bg-surface shadow-token-sm",
              "focus-visible:outline-none focus-visible:[box-shadow:var(--focus-ring)]",
            )}
          >
            <span
              aria-hidden="true"
              className={cn(
                "grid size-5 place-items-center rounded-full font-mono text-[10px] font-semibold",
                appearance.className,
              )}
              style={appearance.style}
            >
              {renderNodeContent({ status, number })}
            </span>
            <div className="min-w-0">
              <div className="truncate text-[12.5px] font-medium text-ink-1">{title}</div>
              {sub ? (
                <div className="mt-0.5 truncate font-mono text-[10.5px] text-ink-3">{sub}</div>
              ) : null}
            </div>
            {meta ? (
              <div className="text-right font-mono text-[10.5px] text-ink-3">{meta}</div>
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}
