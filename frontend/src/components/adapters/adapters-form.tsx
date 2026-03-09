import * as React from "react";
import type { AdaptersConfig, OptimizationConfig, QuantizationConfig } from "@/types/config";
import type {
  AdapterType,
  BiasMode,
  OptimizerType,
  SchedulerType,
  MixedPrecisionMode,
  QuantMode,
  QuantType,
} from "@/types/config";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface AdaptersFormProps {
  readonly adapters: AdaptersConfig;
  readonly optimization: OptimizationConfig;
  readonly quantization: QuantizationConfig;
  readonly onAdaptersChange: (updates: Partial<AdaptersConfig>) => void;
  readonly onOptimizationChange: (updates: Partial<OptimizationConfig>) => void;
  readonly onQuantizationChange: (updates: Partial<QuantizationConfig>) => void;
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

export function AdaptersForm({
  adapters,
  optimization,
  quantization,
  onAdaptersChange,
  onOptimizationChange,
  onQuantizationChange,
}: AdaptersFormProps): React.JSX.Element {
  const [customModule, setCustomModule] = React.useState("");

  const toggleTargetModule = (module: string): void => {
    const current = new Set(adapters.targetModules ?? []);
    if (current.has(module)) {
      current.delete(module);
    } else {
      current.add(module);
    }
    onAdaptersChange({ targetModules: Array.from(current) });
  };

  const addCustomModule = (): void => {
    const trimmed = customModule.trim();
    const currentModules = adapters.targetModules ?? [];
    if (trimmed && !currentModules.includes(trimmed)) {
      onAdaptersChange({ targetModules: [...currentModules, trimmed] });
      setCustomModule("");
    }
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Adapters (PEFT)</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-3">
            <Switch
              id="adapter-toggle"
              checked={adapters.enabled}
              onCheckedChange={(val) => onAdaptersChange({ enabled: val })}
            />
            <Label htmlFor="adapter-toggle">Enable Adapters</Label>
          </div>

          {adapters.enabled && (
            <>
              <div className="space-y-2">
                <Label htmlFor="adapter-type">Adapter Type</Label>
                <Select
                  value={adapters.type}
                  onValueChange={(val) => onAdaptersChange({ type: val as AdapterType })}
                >
                  <SelectTrigger id="adapter-type">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="lora">LoRA</SelectItem>
                    <SelectItem value="qlora">QLoRA</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="lora-rank">Rank (r)</Label>
                  <Input
                    id="lora-rank"
                    type="number"
                    min="1"
                    step="1"
                    value={adapters.rank}
                    onChange={(e) => onAdaptersChange({ rank: Number(e.target.value) })}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="lora-alpha">Alpha</Label>
                  <Input
                    id="lora-alpha"
                    type="number"
                    min="1"
                    step="1"
                    value={adapters.alpha}
                    onChange={(e) => onAdaptersChange({ alpha: Number(e.target.value) })}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="lora-dropout">Dropout</Label>
                  <Input
                    id="lora-dropout"
                    type="number"
                    min="0"
                    max="1"
                    step="0.01"
                    value={adapters.dropout}
                    onChange={(e) => onAdaptersChange({ dropout: Number(e.target.value) })}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="lora-bias">Bias</Label>
                  <Select
                    value={adapters.bias}
                    onValueChange={(val) => onAdaptersChange({ bias: val as BiasMode })}
                  >
                    <SelectTrigger id="lora-bias">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">None</SelectItem>
                      <SelectItem value="all">All</SelectItem>
                      <SelectItem value="lora_only">LoRA Only</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="space-y-2">
                <Label>Target Modules</Label>
                <div className="flex flex-wrap gap-2">
                  {TARGET_MODULE_PRESETS.map((module) => (
                    <button
                      key={module}
                      type="button"
                      onClick={() => toggleTargetModule(module)}
                      className={`px-2 py-1 text-xs rounded border transition-colors ${
                        (adapters.targetModules ?? []).includes(module)
                          ? "bg-primary text-primary-foreground border-primary"
                          : "bg-background border-input hover:bg-accent"
                      }`}
                    >
                      {module}
                    </button>
                  ))}
                </div>
                {(adapters.targetModules ?? [])
                  .filter((m) => !TARGET_MODULE_PRESETS.includes(m))
                  .map((module) => (
                    <div key={module} className="flex items-center gap-2">
                      <span className="text-xs font-mono bg-muted px-2 py-1 rounded">{module}</span>
                      <button
                        type="button"
                        onClick={() => toggleTargetModule(module)}
                        className="text-xs text-destructive hover:underline"
                      >
                        remove
                      </button>
                    </div>
                  ))}
                <div className="flex gap-2">
                  <Input
                    placeholder="custom_module_name"
                    value={customModule}
                    onChange={(e) => setCustomModule(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        addCustomModule();
                      }
                    }}
                    className="text-xs h-8"
                  />
                  <button
                    type="button"
                    onClick={addCustomModule}
                    className="px-3 text-xs rounded border border-input hover:bg-accent"
                  >
                    Add
                  </button>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Optimizer &amp; Scheduler</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label htmlFor="optimizer">Optimizer</Label>
            <Select
              value={optimization.optimizer}
              onValueChange={(val) => onOptimizationChange({ optimizer: val as OptimizerType })}
            >
              <SelectTrigger id="optimizer">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="adamw">AdamW</SelectItem>
                <SelectItem value="adam">Adam</SelectItem>
                <SelectItem value="sgd">SGD</SelectItem>
                <SelectItem value="adafactor">Adafactor</SelectItem>
                <SelectItem value="paged_adamw_8bit">Paged AdamW 8-bit</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="scheduler">LR Scheduler</Label>
            <Select
              value={optimization.scheduler}
              onValueChange={(val) => onOptimizationChange({ scheduler: val as SchedulerType })}
            >
              <SelectTrigger id="scheduler">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="cosine">Cosine</SelectItem>
                <SelectItem value="linear">Linear</SelectItem>
                <SelectItem value="constant">Constant</SelectItem>
                <SelectItem value="constant_with_warmup">Constant with Warmup</SelectItem>
                <SelectItem value="cosine_with_restarts">Cosine with Restarts</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="warmup-ratio">Warmup Ratio</Label>
            <Input
              id="warmup-ratio"
              type="number"
              min="0"
              max="1"
              step="0.01"
              value={optimization.warmupRatio}
              onChange={(e) => onOptimizationChange({ warmupRatio: Number(e.target.value) })}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="mixed-precision">Mixed Precision</Label>
            <Select
              value={optimization.mixedPrecision}
              onValueChange={(val) =>
                onOptimizationChange({ mixedPrecision: val as MixedPrecisionMode })
              }
            >
              <SelectTrigger id="mixed-precision">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="no">None</SelectItem>
                <SelectItem value="fp16">fp16</SelectItem>
                <SelectItem value="bf16">bf16</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="col-span-2 flex items-center gap-3">
            <Switch
              id="grad-checkpoint"
              checked={optimization.gradientCheckpointing}
              onCheckedChange={(val) => onOptimizationChange({ gradientCheckpointing: val })}
            />
            <Label htmlFor="grad-checkpoint">Gradient Checkpointing</Label>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Quantization</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-3">
            <Switch
              id="quant-toggle"
              checked={quantization.enabled}
              onCheckedChange={(val) => onQuantizationChange({ enabled: val })}
            />
            <Label htmlFor="quant-toggle">Enable Quantization</Label>
          </div>

          {quantization.enabled && (
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="quant-mode">Mode</Label>
                <Select
                  value={quantization.mode}
                  onValueChange={(val) => onQuantizationChange({ mode: val as QuantMode })}
                >
                  <SelectTrigger id="quant-mode">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="4bit">4-bit</SelectItem>
                    <SelectItem value="8bit">8-bit</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="quant-type">Quant Type</Label>
                <Select
                  value={quantization.quantType}
                  onValueChange={(val) => onQuantizationChange({ quantType: val as QuantType })}
                >
                  <SelectTrigger id="quant-type">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="nf4">nf4</SelectItem>
                    <SelectItem value="fp4">fp4</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
