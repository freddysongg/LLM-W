import type { ProjectStorageResponse, PerRunStorage } from "@/types/project";
import type { RunStatus } from "@/types/run";
import { fetchApi } from "./client";

interface RawStorageCategoryDetail {
  readonly bytes: number;
  readonly file_count: number;
}

interface RawRunStorageSummary {
  readonly run_id: string;
  readonly total_bytes: number;
  readonly checkpoint_count: number;
  readonly status: string;
}

interface RawRetentionPolicy {
  readonly keep_last_n: number;
  readonly reclaimable_bytes: number;
  readonly reclaimable_checkpoints: number;
}

interface RawProjectStorageResponse {
  readonly project_id: string;
  readonly total_bytes: number;
  readonly breakdown: Record<string, RawStorageCategoryDetail>;
  readonly per_run: ReadonlyArray<RawRunStorageSummary>;
  readonly retention_policy: RawRetentionPolicy;
}

interface RawTotalStorageResponse {
  readonly total_bytes: number;
  readonly per_project: Record<string, number>;
  readonly project_count: number;
}

export interface TotalStorageResponse {
  readonly totalBytes: number;
  readonly perProject: Record<string, number>;
  readonly projectCount: number;
}

function normalizeCategoryDetail(raw: RawStorageCategoryDetail | undefined): {
  bytes: number;
  fileCount: number;
} {
  if (!raw) return { bytes: 0, fileCount: 0 };
  return { bytes: raw.bytes, fileCount: raw.file_count };
}

function normalizePerRun(raw: RawRunStorageSummary): PerRunStorage {
  return {
    runId: raw.run_id,
    totalBytes: raw.total_bytes,
    checkpointCount: raw.checkpoint_count,
    status: raw.status as RunStatus,
  };
}

function normalizeProjectStorage(raw: RawProjectStorageResponse): ProjectStorageResponse {
  return {
    projectId: raw.project_id,
    totalBytes: raw.total_bytes,
    breakdown: {
      checkpoints: normalizeCategoryDetail(raw.breakdown.checkpoints),
      logs: normalizeCategoryDetail(raw.breakdown.logs),
      activations: normalizeCategoryDetail(raw.breakdown.activations),
      exports: normalizeCategoryDetail(raw.breakdown.exports),
      configs: normalizeCategoryDetail(raw.breakdown.configs),
    },
    perRun: raw.per_run.map(normalizePerRun),
    retentionPolicy: {
      keepLastN: raw.retention_policy.keep_last_n,
      reclaimableBytes: raw.retention_policy.reclaimable_bytes,
      reclaimableCheckpoints: raw.retention_policy.reclaimable_checkpoints,
    },
  };
}

export async function fetchProjectStorage({
  projectId,
}: {
  projectId: string;
}): Promise<ProjectStorageResponse> {
  const raw = await fetchApi<RawProjectStorageResponse>({
    path: `/projects/${projectId}/storage`,
  });
  return normalizeProjectStorage(raw);
}

export async function fetchTotalStorage(): Promise<TotalStorageResponse> {
  const raw = await fetchApi<RawTotalStorageResponse>({ path: "/storage/total" });
  return {
    totalBytes: raw.total_bytes,
    perProject: raw.per_project,
    projectCount: raw.project_count,
  };
}

export async function cleanupProjectStorage({ projectId }: { projectId: string }): Promise<void> {
  return fetchApi<void>({
    path: `/projects/${projectId}/storage/cleanup`,
    method: "POST",
  });
}
