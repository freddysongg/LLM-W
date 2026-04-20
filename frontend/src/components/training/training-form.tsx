import * as React from "react";
import type {
  AdaptersConfig,
  ExecutionConfig,
  MixedPrecisionMode,
  OptimizationConfig,
  PreprocessingConfig,
  TrainingConfig,
} from "@/types/config";
import { TrainingConfigTab } from "@/components/training/training-config-tab";
import { TrainingScheduleTab } from "@/components/training/training-schedule-tab";
import { TrainingEnvironmentTab } from "@/components/training/training-environment-tab";

export type TrainingFormTab = "config" | "schedule" | "environment";
export type TrainingMethod = "full" | "lora" | "qlora" | "dpo";
export type TrainingPrecision = MixedPrecisionMode | "int8";

export interface TrainingFormSlice {
  readonly training: TrainingConfig;
  readonly optimization: OptimizationConfig;
  readonly adapters: AdaptersConfig;
  readonly execution: ExecutionConfig;
  readonly preprocessing: PreprocessingConfig;
}

export interface TrainingFormUpdate {
  readonly training?: Partial<TrainingConfig>;
  readonly optimization?: Partial<OptimizationConfig>;
  readonly adapters?: Partial<AdaptersConfig>;
  readonly execution?: Partial<ExecutionConfig>;
  readonly preprocessing?: Partial<PreprocessingConfig>;
}

interface TrainingFormProps {
  readonly slice: TrainingFormSlice;
  readonly activeTab: TrainingFormTab;
  readonly onChange: (update: TrainingFormUpdate) => void;
}

export function TrainingForm({ slice, activeTab, onChange }: TrainingFormProps): React.JSX.Element {
  switch (activeTab) {
    case "config":
      return <TrainingConfigTab slice={slice} onChange={onChange} />;
    case "schedule":
      return <TrainingScheduleTab slice={slice} onChange={onChange} />;
    case "environment":
      return <TrainingEnvironmentTab slice={slice} onChange={onChange} />;
    default: {
      const _exhaustive: never = activeTab;
      return _exhaustive;
    }
  }
}
