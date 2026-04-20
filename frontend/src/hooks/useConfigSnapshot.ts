import { useQuery } from "@tanstack/react-query";

import { fetchConfigSnapshot } from "@/api/config-snapshot";
import type { ConfigSnapshot } from "@/types/config-snapshot";

const CONFIG_SNAPSHOT_KEY = (projectId: string, runId: string) =>
  ["projects", projectId, "runs", runId, "config-snapshot"] as const;

export function useConfigSnapshot({ projectId, runId }: { projectId: string; runId: string }) {
  return useQuery<ConfigSnapshot>({
    queryKey: CONFIG_SNAPSHOT_KEY(projectId, runId),
    queryFn: () => fetchConfigSnapshot({ projectId, runId }),
    enabled: Boolean(projectId) && Boolean(runId),
  });
}
