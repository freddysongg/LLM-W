import * as React from "react";
import type { ToolTraceEntry } from "@/types/voice";

interface VoiceToolTraceProps {
  readonly entries: ReadonlyArray<ToolTraceEntry>;
}

function formatJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

export function VoiceToolTrace({ entries }: VoiceToolTraceProps): React.JSX.Element {
  if (entries.length === 0) {
    return (
      <p className="font-mono text-[11px] text-ink-3">
        Tool calls invoked by the agent will appear here.
      </p>
    );
  }

  return (
    <ul className="space-y-3">
      {entries.map((entry) => (
        <li key={entry.toolCallId} className="rounded border border-hairline bg-surface-1 p-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="font-mono text-[12px] text-ink-1">{entry.name}</span>
            <span className="font-mono text-[10px] text-ink-3">
              {entry.durationMs !== null ? `${entry.durationMs} ms` : "running…"}
            </span>
          </div>
          <details className="group">
            <summary className="cursor-pointer font-mono text-[10px] text-ink-3 group-open:text-ink-2">
              arguments
            </summary>
            <pre className="mt-1 overflow-x-auto rounded bg-surface-2 p-2 font-mono text-[11px] text-ink-1">
              {formatJson(entry.arguments)}
            </pre>
          </details>
          {entry.result !== null && (
            <details className="group mt-2" open>
              <summary className="cursor-pointer font-mono text-[10px] text-ink-3 group-open:text-ink-2">
                result
              </summary>
              <pre className="mt-1 overflow-x-auto rounded bg-surface-2 p-2 font-mono text-[11px] text-ink-1">
                {formatJson(entry.result)}
              </pre>
            </details>
          )}
        </li>
      ))}
    </ul>
  );
}
