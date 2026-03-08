import type { Run, RunStage, MetricPoint, ResumeRunResponse } from "@/types/run";
import type { MetricName } from "@/types/run";
import { fetchApi } from "./client";

export interface LogEntry {
  readonly severity: "debug" | "info" | "warning" | "error" | "critical";
  readonly stage: string | null;
  readonly message: string;
  readonly source: string;
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

export async function fetchRuns({ projectId }: { projectId: string }): Promise<ReadonlyArray<Run>> {
  return fetchApi<ReadonlyArray<Run>>({ path: `/projects/${projectId}/runs` });
}

export async function fetchRun({
  projectId,
  runId,
}: {
  projectId: string;
  runId: string;
}): Promise<Run> {
  return fetchApi<Run>({ path: `/projects/${projectId}/runs/${runId}` });
}

export async function createRun({
  projectId,
  configVersionId,
}: {
  projectId: string;
  configVersionId: string;
}): Promise<Run> {
  return fetchApi<Run>({
    path: `/projects/${projectId}/runs`,
    method: "POST",
    body: { config_version_id: configVersionId },
  });
}

export async function cancelRun({
  projectId,
  runId,
}: {
  projectId: string;
  runId: string;
}): Promise<void> {
  return fetchApi<void>({ path: `/projects/${projectId}/runs/${runId}/cancel`, method: "POST" });
}

export async function pauseRun({
  projectId,
  runId,
}: {
  projectId: string;
  runId: string;
}): Promise<void> {
  return fetchApi<void>({ path: `/projects/${projectId}/runs/${runId}/pause`, method: "POST" });
}

export async function resumeRun({
  projectId,
  runId,
}: {
  projectId: string;
  runId: string;
}): Promise<ResumeRunResponse> {
  return fetchApi<ResumeRunResponse>({
    path: `/projects/${projectId}/runs/${runId}/resume`,
    method: "POST",
  });
}

export async function fetchRunStages({
  projectId,
  runId,
}: {
  projectId: string;
  runId: string;
}): Promise<ReadonlyArray<RunStage>> {
  return fetchApi<ReadonlyArray<RunStage>>({
    path: `/projects/${projectId}/runs/${runId}/stages`,
  });
}

export async function fetchRunMetrics({
  projectId,
  runId,
  params = {},
}: {
  projectId: string;
  runId: string;
  params?: MetricsParams;
}): Promise<ReadonlyArray<MetricPoint>> {
  const searchParams = new URLSearchParams();
  if (params.names) searchParams.set("names", params.names.join(","));
  if (params.stepMin !== undefined) searchParams.set("step_min", String(params.stepMin));
  if (params.stepMax !== undefined) searchParams.set("step_max", String(params.stepMax));
  const query = searchParams.toString();
  return fetchApi<ReadonlyArray<MetricPoint>>({
    path: `/projects/${projectId}/runs/${runId}/metrics${query ? `?${query}` : ""}`,
  });
}

export async function fetchRunLogs({
  projectId,
  runId,
  params = {},
}: {
  projectId: string;
  runId: string;
  params?: LogsParams;
}): Promise<LogsResponse> {
  const searchParams = new URLSearchParams();
  if (params.severity) searchParams.set("severity", params.severity);
  if (params.stage) searchParams.set("stage", params.stage);
  if (params.offset !== undefined) searchParams.set("offset", String(params.offset));
  if (params.limit !== undefined) searchParams.set("limit", String(params.limit));
  const query = searchParams.toString();
  return fetchApi<LogsResponse>({
    path: `/projects/${projectId}/runs/${runId}/logs${query ? `?${query}` : ""}`,
  });
}

export async function fetchCheckpoints({
  projectId,
  runId,
}: {
  projectId: string;
  runId: string;
}): Promise<ReadonlyArray<Checkpoint>> {
  return fetchApi<ReadonlyArray<Checkpoint>>({
    path: `/projects/${projectId}/runs/${runId}/checkpoints`,
  });
}
