import * as React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import type { DataPolicy, ModalGpuType, TrainingEnvironment } from "@/types/config";
import type { TrainingFormSlice, TrainingFormUpdate } from "@/components/training/training-form";

interface TrainingEnvironmentTabProps {
  readonly slice: TrainingFormSlice;
  readonly onChange: (update: TrainingFormUpdate) => void;
}

interface ProviderOption {
  readonly value: TrainingEnvironment;
  readonly label: string;
}

interface GpuTypeOption {
  readonly value: ModalGpuType;
  readonly label: string;
}

const PROVIDER_OPTIONS: ReadonlyArray<ProviderOption> = [
  { value: "modal", label: "modal" },
  { value: "local", label: "local" },
];

const GPU_TYPE_OPTIONS: ReadonlyArray<GpuTypeOption> = [
  { value: "a100-40gb", label: "a100-40gb" },
  { value: "a100-80gb", label: "a100-80gb" },
  { value: "h100", label: "h100" },
  { value: "a10", label: "a10g" },
  { value: "t4", label: "t4" },
];

function policyForEnvironment(environment: TrainingEnvironment): DataPolicy {
  return environment === "modal" ? "sanitized_cloud" : "local_raw";
}

export function TrainingEnvironmentTab({
  slice,
  onChange,
}: TrainingEnvironmentTabProps): React.JSX.Element {
  const { execution } = slice;
  const provider = execution.environment;
  const isModal = provider === "modal";

  return (
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
            {PROVIDER_OPTIONS.map(({ value, label }) => {
              const isActive = provider === value;
              return (
                <button
                  key={value}
                  type="button"
                  onClick={() =>
                    onChange({
                      execution: {
                        environment: value,
                        dataPolicy: policyForEnvironment(value),
                      },
                    })
                  }
                  className={cn(
                    "rounded-sm px-3 py-1.5 font-mono text-[11px] lowercase",
                    "transition-colors duration-[var(--dur-1)]",
                    isActive
                      ? "bg-ink-1 text-[color:var(--surface)]"
                      : "text-ink-2 hover:bg-surface",
                  )}
                >
                  {label}
                </button>
              );
            })}
          </div>
        </div>

        {isModal ? (
          <div className="space-y-4">
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
            <div className="font-mono text-[10.5px] text-ink-3">
              Data policy: <span className="text-ink-1">sanitized_cloud</span>. Raw datasets are not
              allowed to leave the machine — only sanitized artifacts are uploaded.
            </div>
          </div>
        ) : (
          <div className="font-mono text-[10.5px] text-ink-3">
            Local runs use this machine&apos;s device (cuda · mps · cpu, auto-detected).
          </div>
        )}
      </CardContent>
    </Card>
  );
}
