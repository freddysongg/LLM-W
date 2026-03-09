import * as React from "react";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import type { SampleMode } from "@/stores/app-store";
import type { SplitCounts } from "@/types/dataset";

interface DatasetSubsetSelectorProps {
  readonly evalSplit: string | null;
  readonly splitCounts: SplitCounts | null;
  readonly sampleMode: SampleMode;
  readonly maxSamples: number | null;
  readonly totalRows: number | null;
  readonly onEvalSplitChange: (value: string | null) => void;
  readonly onSampleModeChange: (mode: SampleMode) => void;
  readonly onMaxSamplesChange: (value: number | null) => void;
}

type EvalSplitName = "validation" | "test";

const EVAL_SPLIT_OPTIONS: ReadonlyArray<EvalSplitName> = ["validation", "test"];

function formatCount(count: number | null | undefined): string {
  if (count == null) return "";
  return ` (${count.toLocaleString()})`;
}

export function DatasetSubsetSelector({
  evalSplit,
  splitCounts,
  sampleMode,
  maxSamples,
  totalRows,
  onEvalSplitChange,
  onSampleModeChange,
  onMaxSamplesChange,
}: DatasetSubsetSelectorProps): React.JSX.Element {
  const [percentageValue, setPercentageValue] = React.useState<number>(100);

  const handleEvalSplitToggle = (name: EvalSplitName): void => {
    onEvalSplitChange(evalSplit === name ? null : name);
  };

  const handleSampleModeChange = (mode: SampleMode): void => {
    onSampleModeChange(mode);
    if (mode === "all") {
      onMaxSamplesChange(null);
    } else if (mode === "percentage" && totalRows !== null) {
      onMaxSamplesChange(Math.floor((percentageValue / 100) * totalRows));
    } else if (mode === "rows" && maxSamples === null) {
      onMaxSamplesChange(1000);
    }
  };

  const handlePercentageChange = (pct: number): void => {
    setPercentageValue(pct);
    if (totalRows !== null) {
      onMaxSamplesChange(Math.floor((pct / 100) * totalRows));
    }
  };

  const handleRowLimitChange = (raw: string): void => {
    const parsed = parseInt(raw, 10);
    onMaxSamplesChange(Number.isNaN(parsed) || parsed < 1 ? null : parsed);
  };

  const computedRows =
    sampleMode === "percentage" && totalRows !== null
      ? Math.floor((percentageValue / 100) * totalRows)
      : null;

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>Splits</Label>
        <div className="flex gap-2">
          {/* Train is always active — training data is always the train split */}
          <Button type="button" variant="default" size="sm" disabled>
            Train{formatCount(splitCounts?.train)}
          </Button>

          {EVAL_SPLIT_OPTIONS.map((name) => {
            const count =
              name === "validation" ? splitCounts?.validation : splitCounts?.test;
            return (
              <Button
                key={name}
                type="button"
                variant={evalSplit === name ? "default" : "outline"}
                size="sm"
                onClick={() => handleEvalSplitToggle(name)}
              >
                {name.charAt(0).toUpperCase() + name.slice(1)}
                {formatCount(count)}
              </Button>
            );
          })}
        </div>
        <p className="text-xs text-muted-foreground">
          Train is always included. Select Validation or Test as the eval split, or neither to skip
          eval.
        </p>
      </div>

      <div className="space-y-2">
        <Label>Sample size</Label>
        <div className="flex gap-1">
          {(["all", "percentage", "rows"] as const).map((mode) => (
            <Button
              key={mode}
              type="button"
              variant={sampleMode === mode ? "default" : "outline"}
              size="sm"
              disabled={mode === "percentage" && totalRows === null}
              onClick={() => handleSampleModeChange(mode)}
            >
              {mode === "all" ? "All" : mode === "percentage" ? "Percentage" : "Row limit"}
            </Button>
          ))}
        </div>

        {sampleMode === "percentage" && (
          <div className="space-y-1">
            <div className="flex items-center gap-3">
              <Slider
                min={10}
                max={100}
                step={5}
                value={[percentageValue]}
                onValueChange={([pct]) => handlePercentageChange(pct)}
                className="flex-1"
              />
              <span className="text-sm tabular-nums w-12 text-right">{percentageValue}%</span>
            </div>
            {computedRows !== null && (
              <p className="text-xs text-muted-foreground">
                ≈ {computedRows.toLocaleString()} rows
              </p>
            )}
          </div>
        )}

        {sampleMode === "rows" && (
          <Input
            type="number"
            min={1}
            value={maxSamples ?? ""}
            onChange={(e) => handleRowLimitChange(e.target.value)}
            placeholder="e.g. 5000"
          />
        )}

        <p className="text-xs text-muted-foreground">
          {sampleMode === "all" && "All rows from the selected splits will be used."}
          {sampleMode === "percentage" &&
            (totalRows === null
              ? "Resolve the dataset first to enable percentage sampling."
              : "Random slice of the dataset by percentage.")}
          {sampleMode === "rows" && "Maximum number of rows to load from the dataset."}
        </p>
      </div>
    </div>
  );
}
