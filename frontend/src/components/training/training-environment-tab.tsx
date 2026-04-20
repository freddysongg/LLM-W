import * as React from "react";
import { Plus, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";
import type { ModalGpuType, TrainingEnvironment } from "@/types/config";
import type { TrainingFormSlice, TrainingFormUpdate } from "@/components/training/training-form";

interface TrainingEnvironmentTabProps {
  readonly slice: TrainingFormSlice;
  readonly onChange: (update: TrainingFormUpdate) => void;
}

type ProviderOption = TrainingEnvironment | "replicate" | "runpod";
type GpuCount = 1 | 2 | 4 | 8;

const PROVIDER_OPTIONS: ReadonlyArray<{
  readonly value: ProviderOption;
  readonly label: string;
  readonly supported: boolean;
}> = [
  { value: "modal", label: "modal", supported: true },
  { value: "local", label: "local", supported: true },
  { value: "replicate", label: "replicate", supported: false },
  { value: "runpod", label: "runpod", supported: false },
];

const GPU_TYPE_OPTIONS: ReadonlyArray<{
  readonly value: ModalGpuType;
  readonly label: string;
}> = [
  { value: "a100-40gb", label: "a100-40gb" },
  { value: "a100-80gb", label: "a100-80gb" },
  { value: "h100", label: "h100" },
  { value: "a10", label: "a10g" },
  { value: "t4", label: "t4" },
];

const GPU_COUNT_OPTIONS: ReadonlyArray<GpuCount> = [1, 2, 4, 8];

interface IntegrationRow {
  readonly name: string;
  readonly keyHint: string;
}

const INTEGRATION_ROWS: ReadonlyArray<IntegrationRow> = [
  { name: "Weights & Biases", keyHint: "wandb_key" },
  { name: "HuggingFace Hub", keyHint: "hf_token" },
  { name: "Modal", keyHint: "modal_token" },
  { name: "GitHub", keyHint: "github_token" },
];

const INITIAL_ENV_VARS: ReadonlyArray<string> = [
  "WANDB_PROJECT=qwen25",
  "HF_HUB_ENABLE_HF_TRANSFER=1",
];

export function TrainingEnvironmentTab({
  slice,
  onChange,
}: TrainingEnvironmentTabProps): React.JSX.Element {
  const { execution } = slice;
  const provider: ProviderOption = execution.environment;

  const [envVars, setEnvVars] = React.useState<ReadonlyArray<string>>(INITIAL_ENV_VARS);
  const [draftEnvVar, setDraftEnvVar] = React.useState<string>("");
  const [gpuCount, setGpuCount] = React.useState<GpuCount>(1);
  const [integrationToggles, setIntegrationToggles] = React.useState<Record<string, boolean>>({});

  const handleProviderSelect = (nextProvider: ProviderOption): void => {
    if (nextProvider === "replicate" || nextProvider === "runpod") return;
    onChange({ execution: { environment: nextProvider } });
  };

  const handleAddEnvVar = (): void => {
    const trimmed = draftEnvVar.trim();
    if (!trimmed) return;
    if (!trimmed.includes("=")) return;
    setEnvVars((previous) => [...previous, trimmed]);
    setDraftEnvVar("");
  };

  const handleRemoveEnvVar = (target: string): void => {
    setEnvVars((previous) => previous.filter((entry) => entry !== target));
  };

  const handleToggleIntegration = (name: string): void => {
    setIntegrationToggles((previous) => ({ ...previous, [name]: !previous[name] }));
  };

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Compute target</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-2">
            <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-ink-3">
              Provider
            </span>
            <div className="inline-flex rounded-md border border-hairline bg-surface-2 p-0.5">
              {PROVIDER_OPTIONS.map(({ value, label, supported }) => {
                const isActive = provider === value;
                return (
                  <button
                    key={value}
                    type="button"
                    disabled={!supported}
                    onClick={() => handleProviderSelect(value)}
                    className={cn(
                      "rounded-sm px-3 py-1.5 font-mono text-[11px] lowercase",
                      "transition-colors duration-[var(--dur-1)]",
                      isActive
                        ? "bg-ink-1 text-[color:var(--surface)]"
                        : "text-ink-2 hover:bg-surface",
                      !supported && "cursor-not-allowed opacity-40",
                    )}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="space-y-2">
            <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-ink-3">
              GPU type
            </span>
            <Select
              value={execution.modalGpuType ?? "a100-40gb"}
              onValueChange={(value) =>
                onChange({ execution: { modalGpuType: value as ModalGpuType } })
              }
            >
              <SelectTrigger className="w-60">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {GPU_TYPE_OPTIONS.map(({ value, label }) => (
                  <SelectItem key={value} value={value}>
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-ink-3">
              GPU count
            </span>
            <div className="inline-flex rounded-md border border-hairline bg-surface-2 p-0.5">
              {GPU_COUNT_OPTIONS.map((count) => {
                const isActive = gpuCount === count;
                return (
                  <button
                    key={count}
                    type="button"
                    onClick={() => setGpuCount(count)}
                    className={cn(
                      "rounded-sm px-3 py-1.5 font-mono text-[11px]",
                      "transition-colors duration-[var(--dur-1)]",
                      isActive
                        ? "bg-ink-1 text-[color:var(--surface)]"
                        : "text-ink-2 hover:bg-surface",
                    )}
                  >
                    {count}×
                  </button>
                );
              })}
            </div>
          </div>

          <div className="space-y-2">
            <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-ink-3">
              Env vars
            </span>
            <div className="flex flex-wrap items-center gap-2">
              {envVars.map((entry) => (
                <Badge key={entry} variant="secondary" dot={false} className="gap-1.5">
                  <span className="font-mono text-[10px] text-ink-1">{entry}</span>
                  <button
                    type="button"
                    onClick={() => handleRemoveEnvVar(entry)}
                    className="inline-grid size-3 place-items-center text-ink-3 hover:text-ink-1"
                    aria-label={`Remove ${entry}`}
                  >
                    <X className="size-2.5" aria-hidden="true" />
                  </button>
                </Badge>
              ))}
              <div className="flex items-center gap-2">
                <Input
                  mono
                  value={draftEnvVar}
                  onChange={(event) => setDraftEnvVar(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      event.preventDefault();
                      handleAddEnvVar();
                    }
                  }}
                  placeholder="KEY=value"
                  className="h-7 w-40"
                />
                <Button type="button" size="sm" variant="ghost" onClick={handleAddEnvVar}>
                  <Plus className="size-3" aria-hidden="true" />
                  Add
                </Button>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Integrations</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {INTEGRATION_ROWS.map(({ name, keyHint }) => {
            const isOn = integrationToggles[name] ?? false;
            return (
              <div
                key={name}
                className="grid grid-cols-[1fr_auto] items-center gap-4 border-b border-hairline pb-3 last:border-b-0 last:pb-0"
              >
                <div>
                  <div className="text-[12.5px] font-medium text-ink-1">{name}</div>
                  <div className="font-mono text-[10.5px] text-ink-3">{keyHint}</div>
                </div>
                <Switch checked={isOn} onCheckedChange={() => handleToggleIntegration(name)} />
              </div>
            );
          })}
        </CardContent>
      </Card>
    </div>
  );
}
