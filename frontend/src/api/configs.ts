import type { ConfigVersion, SaveConfigRequest, ConfigDiff, ConfigSourceTag } from "@/types/config";
import { fetchApi, fetchTextApi } from "./client";

interface RawConfigDiff {
  readonly added?: Record<string, unknown>;
  readonly removed?: Record<string, unknown>;
  readonly changed?: Record<string, { readonly old: unknown; readonly new: unknown }>;
}

interface RawConfigVersion {
  readonly id: string;
  readonly project_id: string;
  readonly version_number: number;
  readonly yaml_blob?: string;
  readonly yaml_hash: string;
  readonly diff_from_prev: RawConfigDiff | null;
  readonly source_tag: ConfigSourceTag;
  readonly source_detail: string | null;
  readonly created_at: string;
}

interface RawConfigVersionListResponse {
  readonly items: ReadonlyArray<RawConfigVersion>;
  readonly total: number;
  readonly limit: number;
  readonly offset: number;
}

interface RawConfigDiffResponse {
  readonly version_a_id: string;
  readonly version_b_id: string;
  readonly diff: Record<string, unknown>;
}

interface RawConfigValidationResponse {
  readonly is_valid: boolean;
  readonly errors: ReadonlyArray<string>;
}

export interface ConfigVersionListResponse {
  readonly items: ReadonlyArray<ConfigVersion>;
  readonly total: number;
  readonly limit: number;
  readonly offset: number;
}

export interface ConfigDiffResponse {
  readonly versionAId: string;
  readonly versionBId: string;
  readonly diff: Record<string, unknown>;
}

export interface ConfigValidationResponse {
  readonly isValid: boolean;
  readonly errors: ReadonlyArray<string>;
}

function normalizeConfigVersion(raw: RawConfigVersion): ConfigVersion {
  return {
    id: raw.id,
    projectId: raw.project_id,
    versionNumber: raw.version_number,
    // yaml_blob is not returned by the list/get endpoints; use fetchConfigYaml to retrieve content
    yamlBlob: raw.yaml_blob ?? "",
    yamlHash: raw.yaml_hash,
    diffFromPrev: raw.diff_from_prev as ConfigDiff | null,
    sourceTag: raw.source_tag,
    sourceDetail: raw.source_detail,
    createdAt: raw.created_at,
  };
}

export async function fetchActiveConfig({
  projectId,
}: {
  projectId: string;
}): Promise<ConfigVersion> {
  const raw = await fetchApi<RawConfigVersion>({
    path: `/projects/${projectId}/configs/active`,
  });
  const version = normalizeConfigVersion(raw);
  const yamlBlob = await fetchTextApi({
    path: `/projects/${projectId}/configs/${version.id}/yaml`,
  });
  return { ...version, yamlBlob };
}

export async function fetchConfigVersions({
  projectId,
  limit = 20,
  offset = 0,
}: {
  projectId: string;
  limit?: number;
  offset?: number;
}): Promise<ConfigVersionListResponse> {
  const raw = await fetchApi<RawConfigVersionListResponse>({
    path: `/projects/${projectId}/configs?limit=${limit}&offset=${offset}`,
  });
  return {
    items: raw.items.map(normalizeConfigVersion),
    total: raw.total,
    limit: raw.limit,
    offset: raw.offset,
  };
}

export async function fetchConfigVersion({
  projectId,
  versionId,
}: {
  projectId: string;
  versionId: string;
}): Promise<ConfigVersion> {
  const raw = await fetchApi<RawConfigVersion>({
    path: `/projects/${projectId}/configs/${versionId}`,
  });
  return normalizeConfigVersion(raw);
}

export async function saveConfig({
  projectId,
  request,
}: {
  projectId: string;
  request: SaveConfigRequest;
}): Promise<ConfigVersion> {
  const raw = await fetchApi<RawConfigVersion>({
    path: `/projects/${projectId}/configs`,
    method: "PUT",
    body: {
      yaml_content: request.yamlContent,
      source_tag: request.sourceTag,
      source_detail: request.sourceDetail ?? null,
    },
  });
  return normalizeConfigVersion(raw);
}

export async function fetchConfigDiff({
  projectId,
  versionId,
  otherVersionId,
}: {
  projectId: string;
  versionId: string;
  otherVersionId: string;
}): Promise<ConfigDiffResponse> {
  const raw = await fetchApi<RawConfigDiffResponse>({
    path: `/projects/${projectId}/configs/${versionId}/diff/${otherVersionId}`,
  });
  return {
    versionAId: raw.version_a_id,
    versionBId: raw.version_b_id,
    diff: raw.diff,
  };
}

export async function validateConfig({
  projectId,
  versionId,
}: {
  projectId: string;
  versionId: string;
}): Promise<ConfigValidationResponse> {
  const raw = await fetchApi<RawConfigValidationResponse>({
    path: `/projects/${projectId}/configs/${versionId}/validate`,
    method: "POST",
  });
  return { isValid: raw.is_valid, errors: raw.errors };
}

export async function fetchConfigYaml({
  projectId,
  versionId,
}: {
  projectId: string;
  versionId: string;
}): Promise<string> {
  return fetchTextApi({ path: `/projects/${projectId}/configs/${versionId}/yaml` });
}
