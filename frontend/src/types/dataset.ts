import type { DatasetSource, DatasetFormat } from "./config";

export interface TokenStats {
  readonly min: number;
  readonly max: number;
  readonly mean: number;
  readonly median: number;
  readonly p95: number;
}

export interface QualityWarning {
  readonly type: string;
  readonly message: string;
  readonly count: number | null;
}

export interface SampleRow {
  readonly index: number;
  readonly fields: Record<string, string>;
}

export interface DatasetProfile {
  readonly id: string;
  readonly projectId: string;
  readonly source: DatasetSource;
  readonly datasetId: string;
  readonly fingerprint: string | null;
  readonly trainSize: number | null;
  readonly evalSize: number | null;
  readonly fieldMapping: Record<string, string> | null;
  readonly tokenStats: TokenStats | null;
  readonly qualityWarnings: ReadonlyArray<QualityWarning>;
  readonly format: DatasetFormat;
  readonly createdAt: string;
  readonly updatedAt: string;
}
