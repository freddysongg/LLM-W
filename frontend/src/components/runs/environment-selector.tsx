import * as React from "react";
import { AlertCircle } from "lucide-react";
import type { TrainingEnvironment, ModalGpuType } from "@/types/run";
import { MODAL_GPU_OPTIONS } from "@/api/cloud";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";

interface EnvironmentSelectorProps {
  readonly environment: TrainingEnvironment;
  readonly onEnvironmentChange: (env: TrainingEnvironment) => void;
  readonly modalGpuType: ModalGpuType | null;
  readonly onModalGpuTypeChange: (gpu: ModalGpuType) => void;
  readonly isModalTokenSet: boolean;
}

export function EnvironmentSelector({
  environment,
  onEnvironmentChange,
  modalGpuType,
  onModalGpuTypeChange,
  isModalTokenSet,
}: EnvironmentSelectorProps): React.JSX.Element {
  return (
    <div className="flex items-center gap-3">
      <div className="flex items-center gap-2">
        <Label className="text-sm text-muted-foreground whitespace-nowrap">Environment</Label>
        <Select
          value={environment}
          onValueChange={(v) => onEnvironmentChange(v as TrainingEnvironment)}
        >
          <SelectTrigger className="w-36 h-8 text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="local">Local</SelectItem>
            <SelectItem value="modal">Modal Cloud</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {environment === "modal" && !isModalTokenSet && (
        <div className="flex items-center gap-1.5 text-xs text-amber-600">
          <AlertCircle className="h-3.5 w-3.5 shrink-0" />
          <span>
            No Modal token configured.{" "}
            <a href="/settings" className="underline underline-offset-2 hover:text-amber-700">
              Go to Settings
            </a>
          </span>
        </div>
      )}

      {environment === "modal" && isModalTokenSet && (
        <div className="flex items-center gap-2">
          <Label className="text-sm text-muted-foreground whitespace-nowrap">GPU</Label>
          <Select
            value={modalGpuType ?? ""}
            onValueChange={(v) => onModalGpuTypeChange(v as ModalGpuType)}
          >
            <SelectTrigger className="w-52 h-8 text-xs">
              <SelectValue placeholder="Select GPU tier" />
            </SelectTrigger>
            <SelectContent>
              {MODAL_GPU_OPTIONS.map(({ value, label, pricePerHour }) => (
                <SelectItem key={value} value={value}>
                  <span className="flex items-center justify-between w-full gap-4">
                    <span>{label}</span>
                    <span className="text-muted-foreground">${pricePerHour.toFixed(2)}/hr</span>
                  </span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}
    </div>
  );
}
