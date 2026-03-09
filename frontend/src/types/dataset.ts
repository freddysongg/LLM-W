import type { DatasetSource, DatasetFormat } from "./config";

export interface TokenStats {
  readonly min: number;
  readonly max: number;
  readonly mean: number;
  readonly median: number;
  readonly p95: number;
  readonly p99: number;
}

export interface SplitCounts {
  readonly train: number | null;
  readonly validation: number | null;
  readonly test: number | null;
}

export interface QualityWarning {
  readonly code: string;
  readonly message: string;
  readonly count: number | null;
}

export interface DatasetSample {
  readonly index: number;
  readonly row: Record<string, unknown>;
}

export interface DatasetProfile {
  readonly datasetId: string;
  readonly source: DatasetSource;
  readonly format: DatasetFormat;
  readonly totalRows: number;
  readonly splitCounts: SplitCounts;
  readonly detectedFields: ReadonlyArray<string>;
  readonly tokenStats: TokenStats | null;
  readonly qualityWarnings: ReadonlyArray<QualityWarning>;
  readonly duplicateCount: number;
  readonly malformedCount: number;
  readonly resolvedAt: string;
}

export interface DatasetSamplesResponse {
  readonly total: number;
  readonly offset: number;
  readonly limit: number;
  readonly samples: ReadonlyArray<DatasetSample>;
}

export interface DatasetResolveRequest {
  readonly source: DatasetSource;
  readonly datasetId: string;
  readonly subset: string | null;
  readonly trainSplit: string;
  readonly evalSplit: string | null;
  readonly format: DatasetFormat;
  readonly formatMapping: Record<string, string> | null;
  readonly maxSamples: number | null;
  readonly trainRatio: number | null;
  readonly valRatio: number | null;
  readonly testRatio: number | null;
}

export interface PreviewTransformRequest {
  readonly format: DatasetFormat;
  readonly formatMapping: Record<string, string> | null;
  readonly sampleCount: number;
}

export interface PreviewTransformResponse {
  readonly samples: ReadonlyArray<Record<string, unknown>>;
  readonly formatApplied: string;
  readonly truncated: boolean;
}
