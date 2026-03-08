import * as React from "react";
import type { ArtifactType } from "@/types/artifact";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const ARTIFACT_TYPES: ReadonlyArray<{ value: ArtifactType; label: string }> = [
  { value: "checkpoint", label: "Checkpoint" },
  { value: "config_snapshot", label: "Config Snapshot" },
  { value: "eval_output", label: "Eval Output" },
  { value: "metric_export", label: "Metric Export" },
  { value: "comparison_summary", label: "Comparison Summary" },
  { value: "ai_recommendation", label: "AI Recommendation" },
  { value: "log_file", label: "Log File" },
  { value: "activation_summary", label: "Activation Summary" },
  { value: "weight_delta", label: "Weight Delta" },
];

interface TypeFilterProps {
  readonly value: ArtifactType | undefined;
  readonly onChange: (value: ArtifactType | undefined) => void;
}

export function TypeFilter({ value, onChange }: TypeFilterProps): React.JSX.Element {
  const handleChange = (selected: string): void => {
    onChange(selected === "all" ? undefined : (selected as ArtifactType));
  };

  return (
    <Select value={value ?? "all"} onValueChange={handleChange}>
      <SelectTrigger className="w-48">
        <SelectValue placeholder="All types" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="all">All types</SelectItem>
        {ARTIFACT_TYPES.map(({ value: typeValue, label }) => (
          <SelectItem key={typeValue} value={typeValue}>
            {label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
