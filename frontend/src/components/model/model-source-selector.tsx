import * as React from "react";
import type { ModelSource } from "@/types/model";

interface ModelSourceSelectorProps {
  readonly source: ModelSource;
  readonly onChange: (source: ModelSource) => void;
}

const SOURCES: ReadonlyArray<{ readonly value: ModelSource; readonly label: string }> = [
  { value: "huggingface", label: "HuggingFace Hub" },
  { value: "local", label: "Local Path" },
];

export function ModelSourceSelector({
  source,
  onChange,
}: ModelSourceSelectorProps): React.JSX.Element {
  return (
    <div className="flex gap-4">
      {SOURCES.map(({ value, label }) => (
        <label key={value} className="flex items-center gap-2 cursor-pointer">
          <input
            type="radio"
            name="model-source"
            value={value}
            checked={source === value}
            onChange={() => onChange(value)}
            className="accent-primary"
          />
          <span className="text-sm">{label}</span>
        </label>
      ))}
    </div>
  );
}
