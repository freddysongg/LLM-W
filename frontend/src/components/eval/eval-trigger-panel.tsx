import * as React from "react";
import type { Run } from "@/types/run";
import type { Rubric } from "@/types/eval";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { TrainingRunSelector } from "./training-run-selector";
import { RubricSelector } from "./rubric-selector";

interface EvalTriggerPanelProps {
  readonly trainingRuns: ReadonlyArray<Run>;
  readonly rubrics: ReadonlyArray<Rubric>;
  readonly selectedTrainingRunId: string | null;
  readonly onSelectTrainingRun: (trainingRunId: string | null) => void;
  readonly selectedVersionIds: ReadonlyArray<string>;
  readonly onToggleVersion: (rubricVersionId: string) => void;
  readonly isUncalibratedVisible: boolean;
  readonly onToggleIsUncalibratedVisible: (isUncalibratedVisible: boolean) => void;
  readonly maxCostUsd: number | null;
  readonly onMaxCostChange: (maxCostUsd: number | null) => void;
  readonly onTriggerEval: () => void;
  readonly isTriggering: boolean;
}

const DEFAULT_MAX_COST_USD = 1.0;
const COST_INPUT_STEP = 0.01;
const COST_INPUT_MIN = 0;

function parseMaxCostInput(rawValue: string): number | null {
  if (rawValue.trim() === "") return null;
  const parsed = Number.parseFloat(rawValue);
  if (Number.isNaN(parsed) || parsed < 0) return null;
  return parsed;
}

export function EvalTriggerPanel({
  trainingRuns,
  rubrics,
  selectedTrainingRunId,
  onSelectTrainingRun,
  selectedVersionIds,
  onToggleVersion,
  isUncalibratedVisible,
  onToggleIsUncalibratedVisible,
  maxCostUsd,
  onMaxCostChange,
  onTriggerEval,
  isTriggering,
}: EvalTriggerPanelProps): React.JSX.Element {
  const canTrigger = selectedVersionIds.length > 0 && !isTriggering;
  const costInputValue = maxCostUsd !== null ? String(maxCostUsd) : "";

  return (
    <div className="rounded-lg border bg-card p-4 space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="space-y-1.5">
          <Label className="text-xs">Training run</Label>
          <TrainingRunSelector
            runs={trainingRuns}
            selectedRunId={selectedTrainingRunId}
            onSelect={onSelectTrainingRun}
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="eval-max-cost" className="text-xs">
            Max cost (USD)
          </Label>
          <Input
            id="eval-max-cost"
            type="number"
            step={COST_INPUT_STEP}
            min={COST_INPUT_MIN}
            value={costInputValue}
            placeholder={String(DEFAULT_MAX_COST_USD)}
            onChange={(event) => onMaxCostChange(parseMaxCostInput(event.target.value))}
            className="w-[140px]"
          />
        </div>

        <Button onClick={onTriggerEval} disabled={!canTrigger}>
          {isTriggering ? "Starting…" : "Run evaluation"}
        </Button>
      </div>

      <RubricSelector
        rubrics={rubrics}
        selectedVersionIds={selectedVersionIds}
        onToggleVersion={onToggleVersion}
        isUncalibratedVisible={isUncalibratedVisible}
        onToggleIsUncalibratedVisible={onToggleIsUncalibratedVisible}
      />
    </div>
  );
}
