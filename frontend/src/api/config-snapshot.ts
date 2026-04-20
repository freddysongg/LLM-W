import type { ConfigDiff, ConfigSnapshot } from "@/types/config-snapshot";
import { fetchApi } from "./client";

interface RawConfigSnapshot {
  readonly run_id: string;
  readonly parent_config_version_id: string;
  readonly yaml: string;
  readonly diff: ConfigDiff;
}

export async function fetchConfigSnapshot({
  projectId,
  runId,
}: {
  projectId: string;
  runId: string;
}): Promise<ConfigSnapshot> {
  const raw = await fetchApi<RawConfigSnapshot>({
    path: `/projects/${projectId}/runs/${runId}/config-snapshot`,
  });
  return {
    runId: raw.run_id,
    parentConfigVersionId: raw.parent_config_version_id,
    yaml: raw.yaml,
    diff: raw.diff,
  };
}
