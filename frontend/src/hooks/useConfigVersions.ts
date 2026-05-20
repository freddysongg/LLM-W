import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { fetchConfigVersions } from "@/api/config-versions";
import type { ConfigVersionList } from "@/types/config-version";

export const CONFIG_VERSIONS_KEY = (projectId: string): readonly [string, string, string] =>
  ["projects", projectId, "config-versions"] as const;

export function useConfigVersions({
  projectId,
  limit = 20,
}: {
  projectId: string;
  limit?: number;
}): UseQueryResult<ConfigVersionList> {
  return useQuery<ConfigVersionList>({
    queryKey: CONFIG_VERSIONS_KEY(projectId),
    queryFn: () => fetchConfigVersions({ projectId, limit }),
    enabled: Boolean(projectId),
  });
}
