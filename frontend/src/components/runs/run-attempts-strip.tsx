import * as React from "react";

import type { RunAttempt } from "@/types/run";

interface RunAttemptsStripProps {
  readonly attempts: ReadonlyArray<RunAttempt>;
}

function describeAttempt(attempt: RunAttempt): string {
  const gpu = attempt.gpuType ?? attempt.device ?? "unknown";
  const reason = attempt.exitReason ?? (attempt.endedAt ? "ended" : "active");
  return `${gpu} · ${reason}`;
}

function pickToneClass(attempt: RunAttempt): string {
  if (attempt.endedAt === null) return "border-primary bg-primary/5 text-ink-1";
  if (attempt.exitReason === "oom") return "border-amber-500/40 bg-amber-500/5 text-ink-2";
  if (attempt.exitReason === "oom_user_cancelled") return "border-hairline bg-surface-2 text-ink-3";
  return "border-hairline bg-surface-2 text-ink-2";
}

export function RunAttemptsStrip({ attempts }: RunAttemptsStripProps): React.JSX.Element | null {
  if (attempts.length <= 1) return null;
  return (
    <div className="flex flex-wrap items-center gap-2" aria-label="Run attempt history">
      {attempts.map((attempt) => (
        <div
          key={attempt.id}
          className={`rounded-md border px-2 py-1 text-[11px] font-mono ${pickToneClass(attempt)}`}
        >
          <span className="opacity-60">#{attempt.attemptIndex}</span>{" "}
          <span>{describeAttempt(attempt)}</span>
        </div>
      ))}
    </div>
  );
}
