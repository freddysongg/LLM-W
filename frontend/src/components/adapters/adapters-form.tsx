import * as React from "react";
import type {
  AdaptersConfig,
  OptimizationConfig,
  QuantizationConfig,
  AdapterType,
  QuantMode,
  QuantComputeDtype,
  MixedPrecisionMode,
} from "@/types/config";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Chip } from "@/components/shared/chip";
import { KVList } from "@/components/shared/kv-list";
import { EffectiveShapeDiagram } from "@/components/adapters/effective-shape-diagram";
import { VramBudgetBar, type VramSegment } from "@/components/adapters/vram-budget-bar";
import { cn } from "@/lib/utils";

export type AdaptersFormSection = "lora" | "quantization" | "memory" | "all";

interface AdaptersFormProps {
  readonly adapters: AdaptersConfig;
  readonly optimization: OptimizationConfig;
  readonly quantization: QuantizationConfig;
  readonly onAdaptersChange: (updates: Partial<AdaptersConfig>) => void;
  readonly onOptimizationChange: (updates: Partial<OptimizationConfig>) => void;
  readonly onQuantizationChange: (updates: Partial<QuantizationConfig>) => void;
  readonly section?: AdaptersFormSection;
  readonly assumedHiddenDim?: number;
}

interface SegmentOption<T extends string> {
  readonly value: T;
  readonly label: string;
}

interface SegmentedControlProps<T extends string> {
  readonly value: T;
  readonly onChange: (next: T) => void;
  readonly options: ReadonlyArray<SegmentOption<T>>;
  readonly ariaLabel: string;
}

function SegmentedControl<T extends string>({
  value,
  onChange,
  options,
  ariaLabel,
}: SegmentedControlProps<T>): React.JSX.Element {
  return (
    <div
      role="radiogroup"
      aria-label={ariaLabel}
      className="inline-flex items-center gap-0.5 rounded-full border border-hairline bg-surface-2 p-[3px]"
    >
      {options.map(({ value: optionValue, label }) => {
        const isActive = value === optionValue;
        return (
          <button
            key={optionValue}
            type="button"
            role="radio"
            aria-checked={isActive}
            onClick={() => onChange(optionValue)}
            className={cn(
              "inline-flex items-center rounded-full px-2.5 py-1",
              "font-mono text-[10px] uppercase leading-none tracking-[0.08em]",
              "transition-colors duration-[var(--dur-1)]",
              "focus-visible:outline-none focus-visible:[box-shadow:var(--focus-ring)]",
              isActive
                ? "bg-ink-1 text-[color:var(--surface)]"
                : "text-ink-2 hover:bg-surface-3 hover:text-ink-1",
            )}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}

const TARGET_MODULE_PRESETS: ReadonlyArray<string> = [
  "q_proj",
  "k_proj",
  "v_proj",
  "o_proj",
  "gate_proj",
  "up_proj",
  "down_proj",
];

const ADAPTER_TYPE_OPTIONS: ReadonlyArray<SegmentOption<AdapterType>> = [
  { value: "lora", label: "LoRA" },
  { value: "qlora", label: "QLoRA" },
];

const QUANT_MODE_OPTIONS: ReadonlyArray<SegmentOption<QuantMode>> = [
  { value: "4bit", label: "4-bit" },
  { value: "8bit", label: "8-bit" },
];

const COMPUTE_DTYPE_OPTIONS: ReadonlyArray<SegmentOption<QuantComputeDtype>> = [
  { value: "float16", label: "fp16" },
  { value: "bfloat16", label: "bf16" },
];

const MIXED_PRECISION_OPTIONS: ReadonlyArray<SegmentOption<MixedPrecisionMode>> = [
  { value: "no", label: "fp32" },
  { value: "bf16", label: "bf16" },
  { value: "fp16", label: "fp16" },
];

const DEFAULT_HIDDEN_DIM = 1536;

function computeTrainablePercentage({
  adapters,
  hiddenDim,
}: {
  readonly adapters: AdaptersConfig;
  readonly hiddenDim: number;
}): number {
  if (!adapters.enabled) return 0;
  const moduleCount = (adapters.targetModules ?? []).length;
  if (moduleCount === 0) return 0;
  const approxTotal = hiddenDim * hiddenDim * 28;
  const approxTrainable = adapters.rank * hiddenDim * 2 * moduleCount * 28;
  return approxTotal > 0 ? (approxTrainable / (approxTotal * 28)) * 100 : 0;
}

function resolveVramSegments({
  optimization,
}: {
  readonly optimization: OptimizationConfig;
}): ReadonlyArray<VramSegment> {
  return [
    { label: "Weights (bf16)", gb: 3.1, color: "oklch(0.82 0.13 310)" },
    {
      label: "Gradients",
      gb: optimization.gradientCheckpointing ? 0.8 : 3.1,
      color: "oklch(0.80 0.14 260)",
    },
    { label: "Optimizer", gb: 3.1, color: "oklch(0.88 0.14 150)" },
    {
      label: "Activations",
      gb: optimization.gradientCheckpointing ? 2.0 : 6.8,
      color: "oklch(0.86 0.11 200)",
    },
  ];
}

interface LoRaSectionProps {
  readonly adapters: AdaptersConfig;
  readonly onAdaptersChange: (updates: Partial<AdaptersConfig>) => void;
  readonly hiddenDim: number;
}

function LoRaSection({
  adapters,
  onAdaptersChange,
  hiddenDim,
}: LoRaSectionProps): React.JSX.Element {
  const selectedModules = adapters.targetModules ?? [];

  const toggleTargetModule = (module: string): void => {
    const current = new Set(selectedModules);
    if (current.has(module)) {
      current.delete(module);
    } else {
      current.add(module);
    }
    onAdaptersChange({ targetModules: Array.from(current) });
  };

  const trainablePercentage = computeTrainablePercentage({ adapters, hiddenDim });
  const alphaRatio = adapters.rank > 0 ? (adapters.alpha / adapters.rank).toFixed(2) : "—";

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>LoRA parameters</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-3">
            <Switch
              id="adapter-toggle"
              checked={adapters.enabled}
              onCheckedChange={(val) => onAdaptersChange({ enabled: val })}
            />
            <Label htmlFor="adapter-toggle" className="font-mono text-[11px] text-ink-2">
              Enable adapters
            </Label>
          </div>

          <div className="space-y-1.5">
            <Label className="font-mono text-[10px] uppercase tracking-[0.08em] text-ink-3">
              Type
            </Label>
            <SegmentedControl
              value={adapters.type}
              onChange={(next) => onAdaptersChange({ type: next })}
              options={ADAPTER_TYPE_OPTIONS}
              ariaLabel="Adapter type"
            />
          </div>

          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <Label className="font-mono text-[10px] uppercase tracking-[0.08em] text-ink-3">
                Rank (r)
              </Label>
              <span className="font-mono text-[11px] text-ink-1">{adapters.rank}</span>
            </div>
            <Slider
              value={[adapters.rank]}
              min={4}
              max={128}
              step={4}
              onValueChange={([value]) => onAdaptersChange({ rank: value })}
            />
          </div>

          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <Label className="font-mono text-[10px] uppercase tracking-[0.08em] text-ink-3">
                Alpha (α)
              </Label>
              <span className="font-mono text-[11px] text-ink-1">{adapters.alpha}</span>
            </div>
            <Slider
              value={[adapters.alpha]}
              min={4}
              max={128}
              step={4}
              onValueChange={([value]) => onAdaptersChange({ alpha: value })}
            />
          </div>

          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <Label className="font-mono text-[10px] uppercase tracking-[0.08em] text-ink-3">
                Dropout
              </Label>
              <span className="font-mono text-[11px] text-ink-1">
                {adapters.dropout.toFixed(2)}
              </span>
            </div>
            <Slider
              value={[adapters.dropout]}
              min={0}
              max={0.3}
              step={0.01}
              onValueChange={([value]) => onAdaptersChange({ dropout: value })}
            />
          </div>

          <div className="space-y-2">
            <Label className="font-mono text-[10px] uppercase tracking-[0.08em] text-ink-3">
              Target modules
            </Label>
            <div className="flex flex-wrap gap-1.5">
              {TARGET_MODULE_PRESETS.map((module) => (
                <Chip
                  key={module}
                  label={module}
                  isOn={selectedModules.includes(module)}
                  onToggle={() => toggleTargetModule(module)}
                />
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Effective shape</CardTitle>
          <Badge variant="iris" dot={false}>
            {trainablePercentage.toFixed(2)}% trainable
          </Badge>
        </CardHeader>
        <CardContent className="space-y-4">
          <EffectiveShapeDiagram rank={adapters.rank} hiddenDim={hiddenDim} />
          <KVList
            rows={[
              { key: "Rank (r)", value: adapters.rank.toString() },
              { key: "Alpha (α)", value: adapters.alpha.toString() },
              { key: "α / r", value: alphaRatio },
              { key: "Targets", value: selectedModules.join(", ") || "—" },
            ]}
          />
        </CardContent>
      </Card>
    </div>
  );
}

interface QuantizationSectionProps {
  readonly quantization: QuantizationConfig;
  readonly onQuantizationChange: (updates: Partial<QuantizationConfig>) => void;
}

function QuantizationSection({
  quantization,
  onQuantizationChange,
}: QuantizationSectionProps): React.JSX.Element {
  const bitsLabel = quantization.mode === "4bit" ? "4" : "8";
  const weightsSizeGb = (1.54 * (quantization.mode === "4bit" ? 4 : 8)) / 8;
  const expectedQuality = quantization.mode === "4bit" ? "~1% degradation" : "lossless";

  return (
    <Card>
      <CardHeader>
        <CardTitle>Quantization</CardTitle>
        <Badge variant="iris" dot={false}>
          {bitsLabel}-bit
        </Badge>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center gap-3">
          <Switch
            id="quant-toggle"
            checked={quantization.enabled}
            onCheckedChange={(val) => onQuantizationChange({ enabled: val })}
          />
          <Label htmlFor="quant-toggle" className="font-mono text-[11px] text-ink-2">
            Enable quantization
          </Label>
        </div>

        <div className="space-y-1.5">
          <Label className="font-mono text-[10px] uppercase tracking-[0.08em] text-ink-3">
            Weight precision
          </Label>
          <SegmentedControl
            value={quantization.mode}
            onChange={(next) => onQuantizationChange({ mode: next })}
            options={QUANT_MODE_OPTIONS}
            ariaLabel="Weight precision"
          />
        </div>

        <div className="space-y-1.5">
          <Label className="font-mono text-[10px] uppercase tracking-[0.08em] text-ink-3">
            Compute dtype
          </Label>
          <SegmentedControl
            value={quantization.computeDtype}
            onChange={(next) => onQuantizationChange({ computeDtype: next })}
            options={COMPUTE_DTYPE_OPTIONS}
            ariaLabel="Compute dtype"
          />
        </div>

        <KVList
          rows={[
            { key: "Weights size", value: `${weightsSizeGb.toFixed(2)} GB` },
            { key: "VRAM (est)", value: `${(weightsSizeGb + 6).toFixed(1)} GB` },
            { key: "Quality", value: expectedQuality },
            { key: "Double quant", value: quantization.doubleQuant ? "yes" : "no" },
          ]}
        />
      </CardContent>
    </Card>
  );
}

interface MemorySectionProps {
  readonly optimization: OptimizationConfig;
  readonly onOptimizationChange: (updates: Partial<OptimizationConfig>) => void;
}

function MemorySection({
  optimization,
  onOptimizationChange,
}: MemorySectionProps): React.JSX.Element {
  const segments = resolveVramSegments({ optimization });

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Memory strategies</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <Label htmlFor="grad-checkpoint" className="font-mono text-[11px] text-ink-2">
              Gradient checkpointing
            </Label>
            <Switch
              id="grad-checkpoint"
              checked={optimization.gradientCheckpointing}
              onCheckedChange={(val) => onOptimizationChange({ gradientCheckpointing: val })}
            />
          </div>

          <div className="space-y-1.5">
            <Label className="font-mono text-[10px] uppercase tracking-[0.08em] text-ink-3">
              Mixed precision
            </Label>
            <SegmentedControl
              value={optimization.mixedPrecision}
              onChange={(next) => onOptimizationChange({ mixedPrecision: next })}
              options={MIXED_PRECISION_OPTIONS}
              ariaLabel="Mixed precision"
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>VRAM budget</CardTitle>
        </CardHeader>
        <CardContent>
          <VramBudgetBar segments={segments} totalGb={40} />
        </CardContent>
      </Card>
    </div>
  );
}

export function AdaptersForm({
  adapters,
  optimization,
  quantization,
  onAdaptersChange,
  onOptimizationChange,
  onQuantizationChange,
  section = "all",
  assumedHiddenDim = DEFAULT_HIDDEN_DIM,
}: AdaptersFormProps): React.JSX.Element {
  if (section === "lora") {
    return (
      <LoRaSection
        adapters={adapters}
        onAdaptersChange={onAdaptersChange}
        hiddenDim={assumedHiddenDim}
      />
    );
  }

  if (section === "quantization") {
    return (
      <QuantizationSection
        quantization={quantization}
        onQuantizationChange={onQuantizationChange}
      />
    );
  }

  if (section === "memory") {
    return (
      <MemorySection optimization={optimization} onOptimizationChange={onOptimizationChange} />
    );
  }

  return (
    <div className="space-y-4">
      <LoRaSection
        adapters={adapters}
        onAdaptersChange={onAdaptersChange}
        hiddenDim={assumedHiddenDim}
      />
      <QuantizationSection
        quantization={quantization}
        onQuantizationChange={onQuantizationChange}
      />
      <MemorySection optimization={optimization} onOptimizationChange={onOptimizationChange} />
    </div>
  );
}
