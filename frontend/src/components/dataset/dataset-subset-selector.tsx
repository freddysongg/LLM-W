import * as React from "react";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import type { SampleMode } from "@/stores/app-store";
import type { SplitCounts } from "@/types/dataset";

type SplitField = "train" | "val" | "test";

interface DatasetSubsetSelectorProps {
  readonly trainRatio: number | null;
  readonly valRatio: number | null;
  readonly testRatio: number | null;
  readonly splitCounts: SplitCounts | null;
  readonly sampleMode: SampleMode;
  readonly maxSamples: number | null;
  readonly totalRows: number | null;
  readonly onTrainRatioChange: (value: number | null) => void;
  readonly onValRatioChange: (value: number | null) => void;
  readonly onTestRatioChange: (value: number | null) => void;
  readonly onSampleModeChange: (mode: SampleMode) => void;
  readonly onMaxSamplesChange: (value: number | null) => void;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export function DatasetSubsetSelector({
  trainRatio,
  valRatio,
  testRatio,
  splitCounts,
  sampleMode,
  maxSamples,
  totalRows,
  onTrainRatioChange,
  onValRatioChange,
  onTestRatioChange,
  onSampleModeChange,
  onMaxSamplesChange,
}: DatasetSubsetSelectorProps): React.JSX.Element {
  const [percentageValue, setPercentageValue] = React.useState<number>(100);
  const lastEdited = React.useRef<SplitField | null>(null);

  const handleRatioChange = (field: SplitField, raw: string): void => {
    lastEdited.current = field;
    const parsed = parseInt(raw, 10);
    const entered = Number.isNaN(parsed) ? null : clamp(parsed, 0, 100);

    const next = { train: trainRatio, val: valRatio, test: testRatio, [field]: entered };

    // Auto-fill the third field when the other two are set
    const { train, val, test } = next;
    if (field !== "test" && train !== null && val !== null) {
      next.test = clamp(100 - train - val, 0, 100);
    } else if (field !== "val" && train !== null && test !== null) {
      next.val = clamp(100 - train - test, 0, 100);
    } else if (field !== "train" && val !== null && test !== null) {
      next.train = clamp(100 - val - test, 0, 100);
    }

    onTrainRatioChange(next.train);
    onValRatioChange(next.val);
    onTestRatioChange(next.test);
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

  const sum =
    (trainRatio ?? 0) + (valRatio ?? 0) + (testRatio ?? 0);
  const hasValues = trainRatio !== null || valRatio !== null || testRatio !== null;
  const isInvalid = hasValues && sum !== 100;

  const computedRows =
    sampleMode === "percentage" && totalRows !== null
      ? Math.floor((percentageValue / 100) * totalRows)
      : null;

  const estimateRow = (ratio: number | null): string | null => {
    if (ratio === null || totalRows === null) return null;
    return `≈ ${Math.floor((ratio / 100) * totalRows).toLocaleString()} rows`;
  };

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>Split ratios</Label>
        <div className="grid grid-cols-3 gap-3">
          {(
            [
              { field: "train" as SplitField, label: "Train", ratio: trainRatio, resolved: splitCounts?.train ?? null },
              { field: "val" as SplitField, label: "Validation", ratio: valRatio, resolved: splitCounts?.validation ?? null },
              { field: "test" as SplitField, label: "Test", ratio: testRatio, resolved: splitCounts?.test ?? null },
            ] as const
          ).map(({ field, label, ratio, resolved }) => (
            <div key={field} className="space-y-1">
              <Label className="text-xs text-muted-foreground">{label}</Label>
              <div className="flex items-center gap-1">
                <Input
                  type="number"
                  min={0}
                  max={100}
                  value={ratio ?? ""}
                  onChange={(e) => handleRatioChange(field, e.target.value)}
                  placeholder="—"
                  className="w-full"
                />
                <span className="text-xs text-muted-foreground shrink-0">%</span>
              </div>
              {estimateRow(ratio) !== null && (
                <p className="text-xs text-muted-foreground">{estimateRow(ratio)}</p>
              )}
              {resolved !== null && (
                <p className="text-xs text-muted-foreground">
                  resolved: {resolved.toLocaleString()}
                </p>
              )}
            </div>
          ))}
        </div>
        {isInvalid && (
          <p className="text-xs text-destructive">Percentages must sum to 100 (currently {sum})</p>
        )}
        <p className="text-xs text-muted-foreground">
          Set two values and the third auto-fills. Leave all blank to skip ratio tracking.
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
