import type { StorageCategory } from "./project";

export type { StorageCategory };

export type ArtifactType =
  | "checkpoint"
  | "config_snapshot"
  | "eval_output"
  | "metric_export"
  | "comparison_summary"
  | "ai_recommendation"
  | "log_file"
  | "activation_summary"
  | "weight_delta";

export interface Artifact {
  readonly id: string;
  readonly runId: string;
  readonly projectId: string;
  readonly artifactType: ArtifactType;
  readonly filePath: string;
  readonly fileSizeBytes: number | null;
  readonly metadata: Record<string, unknown> | null;
  readonly isRetained: boolean;
  readonly createdAt: string;
}

export interface StorageRecord {
  readonly id: string;
  readonly projectId: string;
  readonly category: StorageCategory;
  readonly totalBytes: number;
  readonly fileCount: number;
  readonly lastComputedAt: string;
}
