import * as React from "react";
import type { ModelSource } from "@/types/model";
import { cn } from "@/lib/utils";

interface ModelSourceSelectorProps {
  readonly source: ModelSource;
  readonly onChange: (source: ModelSource) => void;
}

interface SourceOption {
  readonly value: ModelSource;
  readonly label: string;
}

const SOURCES: ReadonlyArray<SourceOption> = [
  { value: "huggingface", label: "HuggingFace" },
  { value: "local", label: "Local path" },
];

export function ModelSourceSelector({
  source,
  onChange,
}: ModelSourceSelectorProps): React.JSX.Element {
  return (
    <div
      role="radiogroup"
      aria-label="Model source"
      className="inline-flex items-center gap-0.5 rounded-full border border-hairline bg-surface-2 p-[3px]"
    >
      {SOURCES.map(({ value, label }) => {
        const isActive = source === value;
        return (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={isActive}
            onClick={() => onChange(value)}
            className={cn(
              "inline-flex items-center rounded-full px-3 py-1",
              "font-mono text-[10px] uppercase leading-none tracking-[0.08em]",
              "transition-colors duration-[var(--dur-1)]",
              "focus-visible:outline-none focus-visible:[box-shadow:var(--focus-ring)]",
              isActive
                ? "bg-ink-1 text-[color:var(--surface)]"
                : "text-ink-2 hover:bg-surface-3 hover:text-ink-1",
            )}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}
