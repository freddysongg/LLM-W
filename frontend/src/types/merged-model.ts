export interface MergedModel {
  readonly id: string;
  readonly projectId: string;
  readonly baseModelId: string;
  readonly sourceRunId: string | null;
  readonly adapterStep: number | null;
  readonly filePath: string;
  readonly fileSizeBytes: number;
  readonly createdAt: string;
}

export interface MergedModelList {
  readonly items: ReadonlyArray<MergedModel>;
  readonly total: number;
}

export interface MergeRunRequest {
  readonly sourceRunId: string;
}
