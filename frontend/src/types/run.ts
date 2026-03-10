export type RunStatus = "pending" | "running" | "completed" | "failed" | "cancelled" | "paused";

export type TrainingEnvironment = "local" | "modal";

export type ModalGpuType = "t4" | "a10" | "a100-40gb" | "a100-80gb" | "h100";

export type StageStatus = "pending" | "running" | "completed" | "failed" | "skipped";

export type StageName =
  | "config_validation"
  | "environment_validation"
  | "model_resolution"
  | "dataset_resolution"
  | "dataset_profiling"
  | "tokenization_preprocessing"
  | "training_preparation"
  | "adapter_attachment"
  | "training_start"
  | "training_progress"
  | "evaluation"
  | "checkpoint_save"
  | "artifact_finalization"
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
  readonly environment?: TrainingEnvironment;
  readonly modalGpuType?: ModalGpuType | null;
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
  readonly resumeFromStep: number | null;
  readonly status: RunStatus;
}

export interface LogEntry {
  readonly severity: "debug" | "info" | "warning" | "error" | "critical";
  readonly stage: string | null;
  readonly message: string;
  readonly source: string | null;
  readonly timestamp: string;
}

export interface LogsResponse {
  readonly logs: ReadonlyArray<LogEntry>;
  readonly total: number;
  readonly hasMore: boolean;
}

export interface MetricsParams {
  readonly names?: ReadonlyArray<MetricName>;
  readonly stepMin?: number;
  readonly stepMax?: number;
}

export interface LogsParams {
  readonly severity?: string;
  readonly stage?: string;
  readonly offset?: number;
  readonly limit?: number;
}

export interface Checkpoint {
  readonly id: string;
  readonly runId: string;
  readonly step: number;
  readonly path: string;
  readonly sizeBytes: number;
  readonly isRetained: boolean;
  readonly createdAt: string;
}
