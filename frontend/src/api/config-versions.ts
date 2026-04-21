import type {
  ConfigValidationResult,
  ConfigVersionList,
  ConfigVersionSummary,
} from "@/types/config-version";
import { fetchApi, fetchTextApi } from "./client";

interface RawSummary {
  readonly id: string;
  readonly project_id: string;
  readonly version_number: number;
  readonly yaml_hash: string;
  readonly diff_from_prev: unknown | null;
  readonly source_tag: string;
  readonly source_detail: string | null;
  readonly created_at: string;
}

interface RawList {
  readonly items: ReadonlyArray<RawSummary>;
  readonly total: number;
  readonly limit: number;
  readonly offset: number;
}

interface RawValidation {
  readonly is_valid: boolean;
  readonly errors: ReadonlyArray<string>;
}

function toSummary(raw: RawSummary): ConfigVersionSummary {
  return {
    id: raw.id,
    projectId: raw.project_id,
    versionNumber: raw.version_number,
    yamlHash: raw.yaml_hash,
    diffFromPrev: raw.diff_from_prev,
    sourceTag: raw.source_tag,
    sourceDetail: raw.source_detail,
    createdAt: raw.created_at,
  };
}

export async function fetchConfigVersions({
  projectId,
  limit = 20,
  offset = 0,
}: {
  projectId: string;
  limit?: number;
  offset?: number;
}): Promise<ConfigVersionList> {
  const raw = await fetchApi<RawList>({
    path: `/projects/${projectId}/configs?limit=${limit}&offset=${offset}`,
  });
  return {
    items: raw.items.map(toSummary),
    total: raw.total,
    limit: raw.limit,
    offset: raw.offset,
  };
}

export async function fetchConfigYamlByVersion({
  projectId,
  versionId,
}: {
  projectId: string;
  versionId: string;
}): Promise<string> {
  return fetchTextApi({
    path: `/projects/${projectId}/configs/${versionId}/yaml`,
  });
}

export async function validateYamlInline({
  projectId,
  yamlContent,
}: {
  projectId: string;
  yamlContent: string;
}): Promise<ConfigValidationResult> {
  const raw = await fetchApi<RawValidation>({
    path: `/projects/${projectId}/configs/validate-inline`,
    method: "POST",
    body: { yaml_content: yamlContent },
  });
  return { isValid: raw.is_valid, errors: raw.errors };
}
