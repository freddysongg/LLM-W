import * as React from "react";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import type { SampleMode } from "@/stores/app-store";

interface DatasetSubsetSelectorProps {
  readonly trainSplit: string;
  readonly evalSplit: string | null;
  readonly sampleMode: SampleMode;
  readonly maxSamples: number | null;
  readonly totalRows: number | null;
  readonly onTrainSplitChange: (value: string) => void;
  readonly onEvalSplitChange: (value: string | null) => void;
  readonly onSampleModeChange: (mode: SampleMode) => void;
  readonly onMaxSamplesChange: (value: number | null) => void;
}

export function DatasetSubsetSelector({
  trainSplit,
  evalSplit,
  sampleMode,
  maxSamples,
  totalRows,
  onTrainSplitChange,
  onEvalSplitChange,
  onSampleModeChange,
  onMaxSamplesChange,
}: DatasetSubsetSelectorProps): React.JSX.Element {
  const [percentageValue, setPercentageValue] = React.useState<number>(100);

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
        <div className="flex gap-3 items-center">
          <div className="flex-1 space-y-1">
            <p className="text-xs text-muted-foreground">Training split</p>
            <Input
              value={trainSplit}
              onChange={(e) => onTrainSplitChange(e.target.value)}
              placeholder="train"
            />
          </div>
          <div className="flex-1 space-y-1">
            <p className="text-xs text-muted-foreground">Eval split</p>
            <div className="flex gap-1">
              <Input
                value={evalSplit ?? ""}
                onChange={(e) => onEvalSplitChange(e.target.value || null)}
                placeholder="validation"
                disabled={evalSplit === null}
              />
              <Button
                type="button"
                variant={evalSplit === null ? "default" : "outline"}
                size="sm"
                className="shrink-0"
                onClick={() => onEvalSplitChange(evalSplit === null ? "validation" : null)}
              >
                {evalSplit === null ? "Add" : "None"}
              </Button>
            </div>
          </div>
        </div>
        <p className="text-xs text-muted-foreground">
          Named splits to load from the dataset. Use &quot;None&quot; to skip eval.
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
