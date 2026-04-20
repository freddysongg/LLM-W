import * as React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Slider } from "@/components/ui/slider";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { SchedulerType } from "@/types/config";
import { LRCurvePreview } from "@/components/training/lr-curve-preview";
import type { TrainingFormSlice, TrainingFormUpdate } from "@/components/training/training-form";

interface TrainingScheduleTabProps {
  readonly slice: TrainingFormSlice;
  readonly onChange: (update: TrainingFormUpdate) => void;
}

const SCHEDULER_OPTIONS: ReadonlyArray<{
  readonly value: SchedulerType;
  readonly label: string;
}> = [
  { value: "cosine", label: "cosine" },
  { value: "linear", label: "linear" },
  { value: "constant", label: "constant" },
  { value: "constant_with_warmup", label: "constant_with_warmup" },
  { value: "cosine_with_restarts", label: "cosine_with_restarts" },
];

const STEPS_PER_EPOCH_ESTIMATE = 1200;
const ESTIMATED_HOURS_PER_EPOCH = 14.2;

export function TrainingScheduleTab({
  slice,
  onChange,
}: TrainingScheduleTabProps): React.JSX.Element {
  const { training, optimization } = slice;
  const totalSteps = Math.max(1, training.epochs * STEPS_PER_EPOCH_ESTIMATE);

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>LR schedule</CardTitle>
          <Select
            value={optimization.scheduler}
            onValueChange={(value) =>
              onChange({ optimization: { scheduler: value as SchedulerType } })
            }
          >
            <SelectTrigger className="w-56">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {SCHEDULER_OPTIONS.map(({ value, label }) => (
                <SelectItem key={value} value={value}>
                  {label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </CardHeader>
        <CardContent>
          <LRCurvePreview
            schedule={optimization.scheduler}
            warmupSteps={optimization.warmupSteps}
            totalSteps={totalSteps}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Checkpoints and eval</CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <ScheduleSliderRow
            label="Warmup steps"
            value={optimization.warmupSteps}
            min={0}
            max={2000}
            step={10}
            formatValue={(value) => value.toFixed(0)}
            onChange={(value) => onChange({ optimization: { warmupSteps: value } })}
          />
          <ScheduleSliderRow
            label="Save checkpoint every"
            value={training.saveSteps}
            min={100}
            max={5000}
            step={100}
            formatValue={(value) => `${value} steps`}
            onChange={(value) => onChange({ training: { saveSteps: value } })}
          />
          <ScheduleSliderRow
            label="Run eval every"
            value={training.evalSteps}
            min={100}
            max={5000}
            step={100}
            formatValue={(value) => `${value} steps`}
            onChange={(value) => onChange({ training: { evalSteps: value } })}
          />
          <div className="flex items-center justify-between border-t border-hairline pt-4">
            <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-ink-3">
              Estimated training time
            </span>
            <span className="font-mono text-[12px] text-ink-1">
              ~ {(training.epochs * ESTIMATED_HOURS_PER_EPOCH).toFixed(1)} hours
            </span>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

interface ScheduleSliderRowProps {
  readonly label: string;
  readonly value: number;
  readonly min: number;
  readonly max: number;
  readonly step: number;
  readonly formatValue: (value: number) => string;
  readonly onChange: (value: number) => void;
}

function ScheduleSliderRow({
  label,
  value,
  min,
  max,
  step,
  formatValue,
  onChange,
}: ScheduleSliderRowProps): React.JSX.Element {
  const handleChange = (values: number[]): void => {
    const next = values[0];
    if (typeof next === "number") onChange(next);
  };
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-[12.5px] text-ink-2">{label}</span>
        <span className="font-mono text-[11px] text-ink-1">{formatValue(value)}</span>
      </div>
      <Slider value={[value]} min={min} max={max} step={step} onValueChange={handleChange} />
    </div>
  );
}
