import * as React from "react";
import type { Run } from "@/types/run";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export const STANDALONE_EVAL_VALUE = "__standalone__" as const;

type TrainingRunSelectionValue = string;

interface TrainingRunSelectorProps {
  readonly runs: ReadonlyArray<Run>;
  readonly selectedRunId: string | null;
  readonly onSelect: (trainingRunId: string | null) => void;
}

export function TrainingRunSelector({
  runs,
  selectedRunId,
  onSelect,
}: TrainingRunSelectorProps): React.JSX.Element {
  const handleValueChange = (nextValue: TrainingRunSelectionValue): void => {
    if (nextValue === STANDALONE_EVAL_VALUE) {
      onSelect(null);
      return;
    }
    onSelect(nextValue);
  };

  const currentValue: TrainingRunSelectionValue = selectedRunId ?? STANDALONE_EVAL_VALUE;

  return (
    <Select value={currentValue} onValueChange={handleValueChange}>
      <SelectTrigger className="w-[260px]">
        <SelectValue placeholder="Select training run" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={STANDALONE_EVAL_VALUE}>Standalone eval (no training run)</SelectItem>
        {runs.map((run) => (
          <SelectItem key={run.id} value={run.id}>
            <span className="font-mono text-xs">{run.id.slice(0, 8)}</span>
            <span className="ml-2 text-xs text-muted-foreground">{run.status}</span>
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
