import * as React from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Slider } from "@/components/ui/slider";
import { cn } from "@/lib/utils";
import type { AdaptersConfig, MixedPrecisionMode } from "@/types/config";
import type {
  TrainingFormSlice,
  TrainingFormUpdate,
  TrainingMethod,
  TrainingPrecision,
} from "@/components/training/training-form";

interface TrainingConfigTabProps {
  readonly slice: TrainingFormSlice;
  readonly onChange: (update: TrainingFormUpdate) => void;
}

interface MethodTile {
  readonly id: TrainingMethod;
  readonly name: string;
  readonly description: string;
  readonly supported: boolean;
}

const METHOD_TILES: ReadonlyArray<MethodTile> = [
  {
    id: "full",
    name: "Full fine-tune",
    description: "All parameters trainable.",
    supported: true,
  },
  {
    id: "lora",
    name: "LoRA",
    description: "Low-rank adapters · fast.",
    supported: true,
  },
  {
    id: "qlora",
    name: "QLoRA",
    description: "4-bit + LoRA · low VRAM.",
    supported: true,
  },
  {
    id: "dpo",
    name: "DPO",
    description: "Preference pairs · unsupported on this config.",
    supported: false,
  },
];

const PRECISION_OPTIONS: ReadonlyArray<{
  readonly value: TrainingPrecision;
  readonly label: string;
}> = [
  { value: "no", label: "fp32" },
  { value: "bf16", label: "bf16" },
  { value: "fp16", label: "fp16" },
  { value: "int8", label: "int8" },
];

function resolveMethod(adapters: AdaptersConfig): TrainingMethod {
  if (!adapters.enabled) return "full";
  if (adapters.type === "qlora") return "qlora";
  return "lora";
}

function methodUpdate(method: TrainingMethod): Partial<AdaptersConfig> | null {
  switch (method) {
    case "full":
      return { enabled: false };
    case "lora":
      return { enabled: true, type: "lora" };
    case "qlora":
      return { enabled: true, type: "qlora" };
    case "dpo":
      return null;
    default: {
      const _exhaustive: never = method;
      return _exhaustive;
    }
  }
}

function resolvePrecision({
  mode,
  isQuantized,
}: {
  readonly mode: MixedPrecisionMode;
  readonly isQuantized: boolean;
}): TrainingPrecision {
  if (isQuantized) return "int8";
  return mode;
}

export function TrainingConfigTab({ slice, onChange }: TrainingConfigTabProps): React.JSX.Element {
  const { training, optimization, adapters, preprocessing } = slice;
  const activeMethod = resolveMethod(adapters);
  const activePrecision = resolvePrecision({
    mode: optimization.mixedPrecision,
    isQuantized: adapters.type === "qlora",
  });
  const effectiveBatchSize = training.batchSize * training.gradientAccumulationSteps;

  const handleMethodSelect = (method: TrainingMethod): void => {
    const update = methodUpdate(method);
    if (!update) return;
    onChange({ adapters: update });
  };

  const handlePrecisionSelect = (precision: TrainingPrecision): void => {
    if (precision === "int8") return;
    onChange({ optimization: { mixedPrecision: precision } });
  };

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Method</CardTitle>
          <Badge variant="secondary" dot={false}>
            parameter-efficient
          </Badge>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-2">
            <div className="font-mono text-[10px] uppercase tracking-[0.1em] text-ink-3">
              Fine-tune strategy
            </div>
            <div className="grid grid-cols-2 gap-3">
              {METHOD_TILES.map(({ id, name, description, supported }) => {
                const isActive = supported && activeMethod === id;
                return (
                  <button
                    key={id}
                    type="button"
                    disabled={!supported}
                    onClick={() => handleMethodSelect(id)}
                    className={cn(
                      "flex flex-col items-start gap-1 rounded-md border px-3 py-2.5 text-left",
                      "transition-colors duration-[var(--dur-1)]",
                      "focus-visible:outline-none focus-visible:[box-shadow:var(--focus-ring)]",
                      isActive
                        ? "border-hairline-strong bg-surface-2"
                        : "border-hairline bg-surface hover:border-hairline-strong hover:bg-surface-2",
                      !supported && "cursor-not-allowed opacity-50",
                    )}
                  >
                    <span className="text-[12.5px] font-medium text-ink-1">{name}</span>
                    <span className="font-mono text-[10.5px] leading-snug text-ink-3">
                      {description}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
          <div className="space-y-2">
            <div className="font-mono text-[10px] uppercase tracking-[0.1em] text-ink-3">
              Precision
            </div>
            <div className="inline-flex rounded-md border border-hairline bg-surface-2 p-0.5">
              {PRECISION_OPTIONS.map(({ value, label }) => {
                const isActive = activePrecision === value;
                const isDisabled = value === "int8";
                return (
                  <button
                    key={value}
                    type="button"
                    disabled={isDisabled}
                    onClick={() => handlePrecisionSelect(value)}
                    className={cn(
                      "rounded-sm px-3 py-1.5 font-mono text-[11px] lowercase leading-none",
                      "transition-colors duration-[var(--dur-1)]",
                      isActive
                        ? "bg-ink-1 text-[color:var(--surface)]"
                        : "text-ink-2 hover:bg-surface",
                      isDisabled && "cursor-not-allowed opacity-40",
                    )}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Hyperparameters</CardTitle>
          <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-ink-3">
            6 params
          </span>
        </CardHeader>
        <CardContent className="space-y-5">
          <SliderRow
            label="Learning rate"
            value={training.learningRate}
            min={1e-6}
            max={1e-3}
            step={1e-6}
            formatValue={(value) => value.toExponential(2)}
            onChange={(value) => onChange({ training: { learningRate: value } })}
          />
          <SliderRow
            label="Batch size"
            value={training.batchSize}
            min={1}
            max={64}
            step={1}
            formatValue={(value) => value.toFixed(0)}
            onChange={(value) => onChange({ training: { batchSize: value } })}
          />
          <SliderRow
            label="Grad accumulation"
            value={training.gradientAccumulationSteps}
            min={1}
            max={32}
            step={1}
            formatValue={(value) => value.toFixed(0)}
            onChange={(value) => onChange({ training: { gradientAccumulationSteps: value } })}
          />
          <SliderRow
            label="Epochs"
            value={training.epochs}
            min={1}
            max={10}
            step={1}
            formatValue={(value) => value.toFixed(0)}
            onChange={(value) => onChange({ training: { epochs: value } })}
          />
          <SliderRow
            label="Max sequence length"
            value={preprocessing.maxSeqLength}
            min={256}
            max={8192}
            step={256}
            formatValue={(value) => value.toFixed(0)}
            onChange={(value) => onChange({ preprocessing: { maxSeqLength: value } })}
          />
          <div className="flex items-center justify-between border-t border-hairline pt-4">
            <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-ink-3">
              Effective batch
            </span>
            <span className="font-mono text-[12px] text-ink-1">
              {training.batchSize} × {training.gradientAccumulationSteps} = {effectiveBatchSize}{" "}
              samples/step
            </span>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

interface SliderRowProps {
  readonly label: string;
  readonly value: number;
  readonly min: number;
  readonly max: number;
  readonly step: number;
  readonly formatValue: (value: number) => string;
  readonly onChange: (value: number) => void;
}

function SliderRow({
  label,
  value,
  min,
  max,
  step,
  formatValue,
  onChange,
}: SliderRowProps): React.JSX.Element {
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
