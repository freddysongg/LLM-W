import type { RunStatus } from "./run";

export type StorageCategory = "checkpoints" | "logs" | "activations" | "exports" | "configs";

export interface StorageCategoryDetail {
  readonly bytes: number;
  readonly fileCount: number;
}

export interface StorageBreakdown {
  readonly checkpoints: StorageCategoryDetail;
  readonly logs: StorageCategoryDetail;
  readonly activations: StorageCategoryDetail;
  readonly exports: StorageCategoryDetail;
  readonly configs: StorageCategoryDetail;
}

export interface PerRunStorage {
  readonly runId: string;
  readonly totalBytes: number;
  readonly checkpointCount: number;
  readonly status: RunStatus;
}

export interface Project {
  readonly id: string;
  readonly name: string;
  readonly description: string;
  readonly directoryPath: string;
  readonly activeConfigVersionId: string | null;
  readonly createdAt: string;
  readonly updatedAt: string;
}

export interface CreateProjectRequest {
  readonly name: string;
  readonly description?: string;
}

export interface UpdateProjectRequest {
  readonly name?: string;
  readonly description?: string;
}

export interface ProjectStorageResponse {
  readonly projectId: string;
  readonly totalBytes: number;
  readonly breakdown: StorageBreakdown;
  readonly perRun: ReadonlyArray<PerRunStorage>;
  readonly retentionPolicy: {
    readonly keepLastN: number;
    readonly reclaimableBytes: number;
    readonly reclaimableCheckpoints: number;
  };
}
