import type {
  DatasetProfile,
  DatasetResolveRequest,
  DatasetSamplesResponse,
  TokenStats,
  PreviewTransformRequest,
  PreviewTransformResponse,
} from "@/types/dataset";
import { fetchApi } from "./client";

interface RawDatasetProfile {
  readonly dataset_id: string;
  readonly source: string;
  readonly format: string;
  readonly total_rows: number;
  readonly split_counts: {
    readonly train: number | null;
    readonly validation: number | null;
    readonly test: number | null;
  };
  readonly detected_fields: ReadonlyArray<string>;
  readonly token_stats: {
    readonly min: number;
    readonly max: number;
    readonly mean: number;
    readonly median: number;
    readonly p95: number;
    readonly p99: number;
  } | null;
  readonly quality_warnings: ReadonlyArray<{
    readonly code: string;
    readonly message: string;
    readonly count: number | null;
  }>;
  readonly duplicate_count: number;
  readonly malformed_count: number;
  readonly resolved_at: string;
}

interface RawPreviewTransformResponse {
  readonly samples: ReadonlyArray<Record<string, unknown>>;
  readonly format_applied: string;
  readonly truncated: boolean;
}

function normalizeProfile(raw: RawDatasetProfile): DatasetProfile {
  return {
    datasetId: raw.dataset_id,
    source: raw.source as DatasetProfile["source"],
    format: raw.format as DatasetProfile["format"],
    totalRows: raw.total_rows,
    splitCounts: {
      train: raw.split_counts.train,
      validation: raw.split_counts.validation,
      test: raw.split_counts.test,
    },
    detectedFields: raw.detected_fields,
    tokenStats: raw.token_stats,
    qualityWarnings: raw.quality_warnings,
    duplicateCount: raw.duplicate_count,
    malformedCount: raw.malformed_count,
    resolvedAt: raw.resolved_at,
  };
}

export async function resolveDataset({
  projectId,
  request,
}: {
  projectId: string;
  request: DatasetResolveRequest;
}): Promise<DatasetProfile> {
  const raw = await fetchApi<RawDatasetProfile>({
    path: `/projects/${projectId}/datasets/resolve`,
    method: "POST",
    body: {
      source: request.source,
      dataset_id: request.datasetId,
      subset: request.subset,
      train_split: request.trainSplit,
      eval_split: request.evalSplit,
      format: request.format,
      format_mapping: request.formatMapping,
      max_samples: request.maxSamples,
    },
  });
  return normalizeProfile(raw);
}

export async function fetchDatasetProfile({
  projectId,
}: {
  projectId: string;
}): Promise<DatasetProfile> {
  const raw = await fetchApi<RawDatasetProfile>({
    path: `/projects/${projectId}/datasets/profile`,
  });
  return normalizeProfile(raw);
}

export async function fetchDatasetSamples({
  projectId,
  limit = 20,
  offset = 0,
}: {
  projectId: string;
  limit?: number;
  offset?: number;
}): Promise<DatasetSamplesResponse> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  return fetchApi<DatasetSamplesResponse>({
    path: `/projects/${projectId}/datasets/samples?${params.toString()}`,
  });
}

export async function fetchTokenStats({ projectId }: { projectId: string }): Promise<TokenStats> {
  return fetchApi<TokenStats>({
    path: `/projects/${projectId}/datasets/token-stats`,
  });
}

export async function previewTransform({
  projectId,
  request,
}: {
  projectId: string;
  request: PreviewTransformRequest;
}): Promise<PreviewTransformResponse> {
  const raw = await fetchApi<RawPreviewTransformResponse>({
    path: `/projects/${projectId}/datasets/preview-transform`,
    method: "POST",
    body: {
      format: request.format,
      format_mapping: request.formatMapping,
      sample_count: request.sampleCount,
    },
  });
  return {
    samples: raw.samples,
    formatApplied: raw.format_applied,
    truncated: raw.truncated,
  };
}
