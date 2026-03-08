import * as React from "react";
import type { DatasetSource } from "@/types/config";
import { Label } from "@/components/ui/label";

interface DatasetSourceSelectorProps {
  readonly value: DatasetSource;
  readonly onChange: (source: DatasetSource) => void;
}

const SOURCES: ReadonlyArray<{ value: DatasetSource; label: string; description: string }> = [
  {
    value: "huggingface",
    label: "HuggingFace",
    description: "Load from HuggingFace Hub using a dataset ID",
  },
  {
    value: "local_jsonl",
    label: "Local JSONL",
    description: "Load from a local .jsonl file (one JSON object per line)",
  },
  {
    value: "local_csv",
    label: "Local CSV",
    description: "Load from a local .csv file with a header row",
  },
  {
    value: "custom",
    label: "Custom",
    description: "Load from a local file with a custom format and field mapping",
  },
];

export function DatasetSourceSelector({
  value,
  onChange,
}: DatasetSourceSelectorProps): React.JSX.Element {
  return (
    <div className="space-y-2">
      <Label>Dataset Source</Label>
      <div className="grid grid-cols-2 gap-2">
        {SOURCES.map((source) => (
          <button
            key={source.value}
            type="button"
            onClick={() => onChange(source.value)}
            className={[
              "flex flex-col items-start gap-1 rounded-md border p-3 text-left text-sm transition-colors",
              value === source.value
                ? "border-primary bg-primary/5"
                : "border-border hover:border-primary/50 hover:bg-muted/50",
            ].join(" ")}
          >
            <span className="font-medium">{source.label}</span>
            <span className="text-xs text-muted-foreground">{source.description}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
