import * as React from "react";
import { cn } from "@/lib/utils";

export type LogLevel = "info" | "warn" | "err" | "debug" | "ok";

export interface LogLine {
  readonly ts: string;
  readonly level: LogLevel;
  readonly msg: string;
}

export interface LogStreamProps {
  readonly lines: readonly LogLine[];
  readonly pinToBottom?: boolean;
  readonly filter?: readonly LogLevel[];
  readonly className?: string;
  readonly height?: number;
}

const LEVEL_COLOR_CLASS: Record<LogLevel, string> = {
  info: "text-ink-3",
  warn: "text-[color:var(--warn)]",
  err: "text-[color:var(--danger)]",
  debug: "text-ink-4",
  ok: "text-[color:var(--success)]",
};

const SCROLL_BOTTOM_THRESHOLD_PX = 24;

function isScrolledToBottom(element: HTMLDivElement): boolean {
  return (
    element.scrollHeight - element.scrollTop - element.clientHeight <= SCROLL_BOTTOM_THRESHOLD_PX
  );
}

export function LogStream({
  lines,
  pinToBottom = true,
  filter,
  className,
  height = 320,
}: LogStreamProps): React.JSX.Element {
  const scrollRef = React.useRef<HTMLDivElement | null>(null);
  const isUserPinnedRef = React.useRef<boolean>(true);

  const visibleLines = React.useMemo<readonly LogLine[]>(() => {
    if (!filter || filter.length === 0) return lines;
    const allowed = new Set<LogLevel>(filter);
    return lines.filter((line) => allowed.has(line.level));
  }, [lines, filter]);

  const handleScroll = (event: React.UIEvent<HTMLDivElement>): void => {
    isUserPinnedRef.current = isScrolledToBottom(event.currentTarget);
  };

  React.useEffect(() => {
    if (!pinToBottom) return;
    const element = scrollRef.current;
    if (!element) return;
    if (!isUserPinnedRef.current) return;
    element.scrollTop = element.scrollHeight;
  }, [visibleLines, pinToBottom]);

  return (
    <div
      ref={scrollRef}
      onScroll={handleScroll}
      role="log"
      aria-live="polite"
      style={{ maxHeight: height }}
      className={cn(
        "overflow-y-auto rounded-md border border-hairline bg-surface font-mono text-[12px] leading-[1.55]",
        className,
      )}
    >
      {visibleLines.map((line, index) => {
        const { ts, level, msg } = line;
        return (
          <div
            key={`${ts}-${index}`}
            className="grid grid-cols-[80px_48px_1fr] gap-2.5 border-l-2 border-transparent px-3.5 py-[3px] hover:bg-surface-2"
          >
            <span className="text-ink-4">{ts}</span>
            <span className={cn("font-semibold uppercase", LEVEL_COLOR_CLASS[level])}>{level}</span>
            <span className="whitespace-pre-wrap break-words text-ink-2">{msg}</span>
          </div>
        );
      })}
    </div>
  );
}

export interface LogStreamToolbarProps {
  readonly value: readonly LogLevel[];
  readonly onChange: (next: readonly LogLevel[]) => void;
  readonly options?: readonly LogLevel[];
  readonly className?: string;
}

const DEFAULT_TOOLBAR_OPTIONS: readonly LogLevel[] = ["info", "warn", "err", "debug", "ok"];

export function LogStreamToolbar({
  value,
  onChange,
  options = DEFAULT_TOOLBAR_OPTIONS,
  className,
}: LogStreamToolbarProps): React.JSX.Element {
  const selected = React.useMemo<Set<LogLevel>>(() => new Set(value), [value]);

  const toggle = (level: LogLevel): void => {
    const next = new Set<LogLevel>(selected);
    if (next.has(level)) {
      next.delete(level);
    } else {
      next.add(level);
    }
    onChange(Array.from(next));
  };

  return (
    <div
      className={cn(
        "inline-flex items-center gap-0.5 rounded-full border border-hairline bg-surface-2 p-[3px]",
        className,
      )}
      role="group"
      aria-label="Log level filter"
    >
      {options.map((level) => {
        const isActive = selected.has(level);
        return (
          <button
            key={level}
            type="button"
            onClick={() => toggle(level)}
            aria-pressed={isActive}
            className={cn(
              "rounded-full px-2.5 py-1 font-mono text-[10px] uppercase leading-none tracking-[0.08em]",
              "transition-colors duration-[var(--dur-1)]",
              isActive ? "bg-ink-1 text-[color:var(--surface)]" : "text-ink-3 hover:text-ink-1",
            )}
          >
            {level}
          </button>
        );
      })}
    </div>
  );
}
