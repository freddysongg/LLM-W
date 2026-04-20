import * as React from "react";
import { AlertCircle } from "lucide-react";
import { Link } from "react-router-dom";
import { MODAL_GPU_OPTIONS } from "@/api/cloud";
import type { ModalGpuType, TrainingEnvironment } from "@/types/config";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

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
  const isModalMissingToken = environment === "modal" && !isModalTokenSet;

  return (
    <div className="flex items-center gap-3">
      <div className="flex items-center gap-2">
        <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-ink-3">env</span>
        <Select
          value={environment}
          onValueChange={(value) => onEnvironmentChange(value as TrainingEnvironment)}
        >
          <SelectTrigger className="w-36">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="local">local</SelectItem>
            <SelectItem value="modal">modal</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {isModalMissingToken ? (
        <div className="flex items-center gap-1.5 font-mono text-[11px] text-[color:var(--warn)]">
          <AlertCircle className="size-3.5 shrink-0" aria-hidden="true" />
          <span>
            No Modal token configured.{" "}
            <Link to="/settings" className="underline underline-offset-2">
              Settings
            </Link>
          </span>
        </div>
      ) : null}

      {environment === "modal" && isModalTokenSet ? (
        <div className="flex items-center gap-2">
          <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-ink-3">gpu</span>
          <Select
            value={modalGpuType ?? ""}
            onValueChange={(value) => onModalGpuTypeChange(value as ModalGpuType)}
          >
            <SelectTrigger className="w-56">
              <SelectValue placeholder="Select GPU tier" />
            </SelectTrigger>
            <SelectContent>
              {MODAL_GPU_OPTIONS.map(({ value, label, pricePerHour }) => (
                <SelectItem key={value} value={value}>
                  <span className="flex w-full items-center justify-between gap-4">
                    <span>{label}</span>
                    <span className="font-mono text-[10px] text-ink-3">
                      ${pricePerHour.toFixed(2)}/hr
                    </span>
                  </span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      ) : null}
    </div>
  );
}
