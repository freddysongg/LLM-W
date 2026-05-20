import * as React from "react";
import { cn } from "@/lib/utils";
import type { TranscriptEntry } from "@/types/voice";

interface VoiceTranscriptProps {
  readonly entries: ReadonlyArray<TranscriptEntry>;
}

export function VoiceTranscript({ entries }: VoiceTranscriptProps): React.JSX.Element {
  const scrollRef = React.useRef<HTMLDivElement | null>(null);

  React.useEffect(() => {
    const node = scrollRef.current;
    if (node) {
      node.scrollTop = node.scrollHeight;
    }
  }, [entries.length]);

  if (entries.length === 0) {
    return (
      <p className="font-mono text-[11px] text-ink-3">
        Transcript will appear here once the agent receives audio.
      </p>
    );
  }

  return (
    <div ref={scrollRef} className="h-full overflow-y-auto pr-2">
      <ul className="space-y-2">
        {entries.map((entry) => (
          <li
            key={entry.index}
            className={cn(
              "rounded border border-hairline px-3 py-2",
              entry.role === "user" ? "bg-surface-2" : "bg-surface-1",
            )}
          >
            <div className="mb-0.5 flex items-center justify-between">
              <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-ink-3">
                {entry.role}
              </span>
              {entry.isInterim && <span className="font-mono text-[9px] text-ink-3">…interim</span>}
            </div>
            <p className="text-[13px] text-ink-1">{entry.text}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}
