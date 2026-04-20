import * as React from "react";
import { cn } from "@/lib/utils";

export type CalloutTone = "iris" | "info" | "warn" | "danger";

export interface CalloutProps {
  readonly title?: string;
  readonly children: React.ReactNode;
  readonly tone?: CalloutTone;
  readonly icon?: React.ReactNode;
  readonly className?: string;
}

const TONE_CLASS: Record<CalloutTone, string> = {
  iris: "border-l-[color:var(--iris-3)] bg-[color-mix(in_oklch,var(--iris-3)_10%,var(--surface))]",
  info: "border-l-[color:var(--info)] bg-[color-mix(in_oklch,var(--info)_10%,var(--surface))]",
  warn: "border-l-[color:var(--warn)] bg-[color-mix(in_oklch,var(--warn)_10%,var(--surface))]",
  danger:
    "border-l-[color:var(--danger)] bg-[color-mix(in_oklch,var(--danger)_10%,var(--surface))]",
};

export function Callout({
  title,
  children,
  tone = "iris",
  icon,
  className,
}: CalloutProps): React.JSX.Element {
  return (
    <aside
      role="note"
      className={cn(
        "flex items-start gap-3 rounded-md border border-hairline border-l-2 p-4 text-[13px] text-ink-1",
        TONE_CLASS[tone],
        className,
      )}
    >
      {icon ? <span className="mt-0.5 shrink-0 text-ink-2">{icon}</span> : null}
      <div className="flex min-w-0 flex-col gap-1">
        {title ? (
          <div className="font-mono text-[11px] uppercase tracking-[0.08em] text-ink-2">
            {title}
          </div>
        ) : null}
        <div className="text-ink-2">{children}</div>
      </div>
    </aside>
  );
}
