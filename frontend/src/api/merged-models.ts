import type { MergedModel, MergedModelList, MergeRunRequest } from "@/types/merged-model";
import { fetchApi } from "./client";

interface RawMergedModel {
  readonly id: string;
  readonly project_id: string;
  readonly base_model_id: string;
  readonly source_run_id: string | null;
  readonly adapter_step: number | null;
  readonly file_path: string;
  readonly file_size_bytes: number;
  readonly created_at: string;
}

interface RawMergedModelList {
  readonly items: ReadonlyArray<RawMergedModel>;
  readonly total: number;
}

function parseMergedModel(raw: RawMergedModel): MergedModel {
  return {
    id: raw.id,
    projectId: raw.project_id,
    baseModelId: raw.base_model_id,
    sourceRunId: raw.source_run_id,
    adapterStep: raw.adapter_step,
    filePath: raw.file_path,
    fileSizeBytes: raw.file_size_bytes,
    createdAt: raw.created_at,
  };
}

export async function fetchMergedModels({
  projectId,
}: {
  projectId: string;
}): Promise<MergedModelList> {
  const raw = await fetchApi<RawMergedModelList>({
    path: `/projects/${projectId}/merged-models`,
  });
  return {
    items: raw.items.map(parseMergedModel),
    total: raw.total,
  };
}

export async function createMergedModel({
  projectId,
  request,
}: {
  projectId: string;
  request: MergeRunRequest;
}): Promise<MergedModel> {
  const raw = await fetchApi<RawMergedModel>({
    path: `/projects/${projectId}/merged-models`,
    method: "POST",
    body: { source_run_id: request.sourceRunId },
  });
  return parseMergedModel(raw);
}

export async function deleteMergedModel({
  projectId,
  mergedId,
}: {
  projectId: string;
  mergedId: string;
}): Promise<void> {
  await fetchApi<void>({
    path: `/projects/${projectId}/merged-models/${mergedId}`,
    method: "DELETE",
  });
}
