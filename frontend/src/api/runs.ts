import type {
  Run,
  RunStage,
  MetricPoint,
  MetricName,
  ResumeRunResponse,
  RunCompareResponse,
  RunMetricSummary,
  RunArtifactSummary,
  LogEntry,
  LogsResponse,
  MetricsParams,
  LogsParams,
  Checkpoint,
  StageName,
  RunStatus,
  StageStatus,
} from "@/types/run";
import { fetchApi } from "./client";

interface RawRun {
  readonly id: string;
  readonly project_id: string;
  readonly config_version_id: string;
  readonly parent_run_id: string | null;
  readonly status: string;
  readonly current_stage: string | null;
  readonly current_step: number;
  readonly total_steps: number | null;
  readonly progress_pct: number;
  readonly started_at: string | null;
  readonly completed_at: string | null;
  readonly failure_reason: string | null;
  readonly failure_stage: string | null;
  readonly last_checkpoint_path: string | null;
  readonly pid: number | null;
  readonly created_at: string;
  readonly updated_at: string;
}

interface RawRunListResponse {
  readonly items: ReadonlyArray<RawRun>;
  readonly total: number;
  readonly limit: number;
  readonly offset: number;
}

interface RawRunStage {
  readonly id: string;
  readonly run_id: string;
  readonly stage_name: string;
  readonly stage_order: number;
  readonly status: string;
  readonly started_at: string | null;
  readonly completed_at: string | null;
  readonly duration_ms: number | null;
  readonly warnings_json: string | null;
  readonly output_summary: string | null;
  readonly created_at: string;
}

interface RawMetricPoint {
  readonly id: string;
  readonly run_id: string;
  readonly step: number;
  readonly epoch: number | null;
  readonly metric_name: string;
  readonly metric_value: number;
  readonly stage_name: string | null;
  readonly recorded_at: string;
}

interface RawResumeRunResponse {
  readonly new_run_id: string;
  readonly parent_run_id: string;
  readonly resume_from_checkpoint: string;
  readonly resume_from_step: number | null;
  readonly status: string;
}

interface RawLogEntry {
  readonly severity: string;
  readonly stage: string | null;
  readonly message: string;
  readonly source: string | null;
  readonly timestamp: string;
}

interface RawLogsResponse {
  readonly lines: ReadonlyArray<RawLogEntry>;
  readonly total: number;
  readonly has_more: boolean;
}

interface RawRunMetricSummary {
  readonly final: number;
  readonly min: number;
  readonly trend: string;
}

interface RawRunArtifactSummary {
  readonly checkpoints: number;
  readonly total_size_mb: number;
}

interface RawRunCompareResponse {
  readonly runs: ReadonlyArray<string>;
  readonly config_diff: Record<string, Record<string, Record<string, unknown>>>;
  readonly metric_comparison: Record<string, Record<string, RawRunMetricSummary>>;
  readonly artifact_comparison: Record<string, RawRunArtifactSummary>;
}

interface RawCheckpoint {
  readonly id: string;
  readonly run_id: string;
  readonly project_id: string;
  readonly step: number | null;
  readonly file_path: string;
  readonly file_size_bytes: number | null;
  readonly metadata_json: string | null;
  readonly is_retained: boolean;
  readonly created_at: string;
}

function normalizeRun(raw: RawRun): Run {
  return {
    id: raw.id,
    projectId: raw.project_id,
    configVersionId: raw.config_version_id,
    parentRunId: raw.parent_run_id,
    status: raw.status as RunStatus,
    currentStage: raw.current_stage as StageName | null,
    currentStep: raw.current_step,
    totalSteps: raw.total_steps,
    progressPct: raw.progress_pct,
    startedAt: raw.started_at,
    completedAt: raw.completed_at,
    failureReason: raw.failure_reason,
    failureStage: raw.failure_stage as StageName | null,
    lastCheckpointPath: raw.last_checkpoint_path,
    // heartbeat_path is not included in RunResponse — backend gap
    heartbeatPath: null,
    pid: raw.pid,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
  };
}

function normalizeRunStage(raw: RawRunStage): RunStage {
  let warnings: ReadonlyArray<string> = [];
  if (raw.warnings_json) {
    try {
      warnings = JSON.parse(raw.warnings_json) as ReadonlyArray<string>;
    } catch {
      // malformed warnings_json — treat as empty
    }
  }
  return {
    id: raw.id,
    runId: raw.run_id,
    stageName: raw.stage_name as StageName,
    stageOrder: raw.stage_order,
    status: raw.status as StageStatus,
    startedAt: raw.started_at,
    completedAt: raw.completed_at,
    durationMs: raw.duration_ms,
    warnings,
    outputSummary: raw.output_summary,
    // log_tail is not included in RunStageResponse — backend gap
    logTail: null,
    createdAt: raw.created_at,
  };
}

function normalizeMetricPoint(raw: RawMetricPoint): MetricPoint {
  return {
    id: raw.id,
    runId: raw.run_id,
    step: raw.step,
    epoch: raw.epoch,
    metricName: raw.metric_name as MetricName,
    metricValue: raw.metric_value,
    stageName: raw.stage_name as StageName | null,
    recordedAt: raw.recorded_at,
  };
}

function normalizeResumeRunResponse(raw: RawResumeRunResponse): ResumeRunResponse {
  return {
    newRunId: raw.new_run_id,
    parentRunId: raw.parent_run_id,
    checkpointPath: raw.resume_from_checkpoint,
    resumeFromStep: raw.resume_from_step,
    status: raw.status as RunStatus,
  };
}

function normalizeLogEntry(raw: RawLogEntry): LogEntry {
  return {
    severity: raw.severity as LogEntry["severity"],
    stage: raw.stage,
    message: raw.message,
    source: raw.source,
    timestamp: raw.timestamp,
  };
}

function normalizeMetricSummary(raw: RawRunMetricSummary): RunMetricSummary {
  return { final: raw.final, min: raw.min, trend: raw.trend };
}

function normalizeArtifactSummary(raw: RawRunArtifactSummary): RunArtifactSummary {
  return { checkpoints: raw.checkpoints, totalSizeMb: raw.total_size_mb };
}

function normalizeCheckpoint(raw: RawCheckpoint): Checkpoint {
  return {
    id: raw.id,
    runId: raw.run_id,
    step: raw.step ?? 0,
    path: raw.file_path,
    sizeBytes: raw.file_size_bytes ?? 0,
    isRetained: raw.is_retained,
    createdAt: raw.created_at,
  };
}

function normalizeRunCompare(raw: RawRunCompareResponse): RunCompareResponse {
  const metricComparison: Record<string, Record<string, RunMetricSummary>> = {};
  for (const [metric, byRun] of Object.entries(raw.metric_comparison)) {
    metricComparison[metric] = {};
    for (const [runId, summary] of Object.entries(byRun)) {
      metricComparison[metric][runId] = normalizeMetricSummary(summary);
    }
  }

  const artifactComparison: Record<string, RunArtifactSummary> = {};
  for (const [runId, summary] of Object.entries(raw.artifact_comparison)) {
    artifactComparison[runId] = normalizeArtifactSummary(summary);
  }

  return {
    runs: raw.runs,
    configDiff: raw.config_diff,
    metricComparison,
    artifactComparison,
  };
}

export async function fetchRuns({ projectId }: { projectId: string }): Promise<ReadonlyArray<Run>> {
  const raw = await fetchApi<RawRunListResponse>({ path: `/projects/${projectId}/runs` });
  return raw.items.map(normalizeRun);
}

export async function fetchRun({
  projectId,
  runId,
}: {
  projectId: string;
  runId: string;
}): Promise<Run> {
  const raw = await fetchApi<RawRun>({ path: `/projects/${projectId}/runs/${runId}` });
  return normalizeRun(raw);
}

export async function createRun({
  projectId,
  configVersionId,
}: {
  projectId: string;
  configVersionId: string;
}): Promise<Run> {
  const raw = await fetchApi<RawRun>({
    path: `/projects/${projectId}/runs`,
    method: "POST",
    body: { config_version_id: configVersionId },
  });
  return normalizeRun(raw);
}

export async function deleteRun({
  projectId,
  runId,
}: {
  projectId: string;
  runId: string;
}): Promise<void> {
  return fetchApi<void>({ path: `/projects/${projectId}/runs/${runId}`, method: "DELETE" });
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
  const raw = await fetchApi<RawResumeRunResponse>({
    path: `/projects/${projectId}/runs/${runId}/resume`,
    method: "POST",
  });
  return normalizeResumeRunResponse(raw);
}

export async function fetchRunStages({
  projectId,
  runId,
}: {
  projectId: string;
  runId: string;
}): Promise<ReadonlyArray<RunStage>> {
  const raw = await fetchApi<ReadonlyArray<RawRunStage>>({
    path: `/projects/${projectId}/runs/${runId}/stages`,
  });
  return raw.map(normalizeRunStage);
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
  const raw = await fetchApi<ReadonlyArray<RawMetricPoint>>({
    path: `/projects/${projectId}/runs/${runId}/metrics${query ? `?${query}` : ""}`,
  });
  return raw.map(normalizeMetricPoint);
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
  const raw = await fetchApi<RawLogsResponse>({
    path: `/projects/${projectId}/runs/${runId}/logs${query ? `?${query}` : ""}`,
  });
  return {
    logs: raw.lines.map(normalizeLogEntry),
    total: raw.total,
    hasMore: raw.has_more,
  };
}

export async function fetchCheckpoints({
  projectId,
  runId,
}: {
  projectId: string;
  runId: string;
}): Promise<ReadonlyArray<Checkpoint>> {
  const raw = await fetchApi<ReadonlyArray<RawCheckpoint>>({
    path: `/projects/${projectId}/runs/${runId}/checkpoints`,
  });
  return raw.map(normalizeCheckpoint);
}

export async function fetchRunComparison({
  projectId,
  runIds,
}: {
  projectId: string;
  runIds: ReadonlyArray<string>;
}): Promise<RunCompareResponse> {
  const raw = await fetchApi<RawRunCompareResponse>({
    path: `/projects/${projectId}/runs/compare?run_ids=${runIds.join(",")}`,
  });
  return normalizeRunCompare(raw);
}
