export type RunStatus = "pending" | "running" | "completed" | "failed" | "cancelled" | "paused";

export type StageStatus = "pending" | "running" | "completed" | "failed" | "skipped";

export type StageName =
  | "config_validation"
  | "environment_validation"
  | "model_resolution"
  | "dataset_resolution"
  | "preprocessing"
  | "adapter_setup"
  | "quantization_setup"
  | "training_init"
  | "training"
  | "evaluation"
  | "checkpoint_save"
  | "artifact_collection"
  | "cleanup"
  | "completion";

export type MetricName =
  | "train_loss"
  | "eval_loss"
  | "learning_rate"
  | "grad_norm"
  | "tokens_per_second"
  | "step_time_ms"
  | "gpu_memory_used_mb"
  | "gpu_memory_allocated_mb"
  | "cpu_memory_used_mb";

export interface Run {
  readonly id: string;
  readonly projectId: string;
  readonly configVersionId: string;
  readonly parentRunId: string | null;
  readonly status: RunStatus;
  readonly currentStage: StageName | null;
  readonly currentStep: number;
  readonly totalSteps: number | null;
  readonly progressPct: number;
  readonly startedAt: string | null;
  readonly completedAt: string | null;
  readonly failureReason: string | null;
  readonly failureStage: StageName | null;
  readonly lastCheckpointPath: string | null;
  readonly heartbeatPath: string | null;
  readonly pid: number | null;
  readonly createdAt: string;
  readonly updatedAt: string;
}

export interface RunStage {
  readonly id: string;
  readonly runId: string;
  readonly stageName: StageName;
  readonly stageOrder: number;
  readonly status: StageStatus;
  readonly startedAt: string | null;
  readonly completedAt: string | null;
  readonly durationMs: number | null;
  readonly warnings: ReadonlyArray<string>;
  readonly outputSummary: string | null;
  readonly logTail: string | null;
  readonly createdAt: string;
}

export interface MetricPoint {
  readonly id: string;
  readonly runId: string;
  readonly step: number;
  readonly epoch: number | null;
  readonly metricName: MetricName;
  readonly metricValue: number;
  readonly stageName: StageName | null;
  readonly recordedAt: string;
}

export interface RunMetricSummary {
  readonly final: number;
  readonly min: number;
  readonly trend: string;
}

export interface RunArtifactSummary {
  readonly checkpoints: number;
  readonly totalSizeMb: number;
}

export interface RunConfigDiff {
  readonly changed?: Record<string, Record<string, unknown>>;
}

export interface RunCompareResponse {
  readonly runs: ReadonlyArray<string>;
  readonly configDiff: RunConfigDiff;
  readonly metricComparison: Record<string, Record<string, RunMetricSummary>>;
  readonly artifactComparison: Record<string, RunArtifactSummary>;
}

export interface ResumeRunRequest {
  readonly checkpointPath: string;
}

export interface ResumeRunResponse {
  readonly newRunId: string;
  readonly parentRunId: string;
  readonly checkpointPath: string;
}
