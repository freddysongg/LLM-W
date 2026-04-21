import { useQuery } from "@tanstack/react-query";

import { fetchMetricNames } from "@/api/metric-names";
import type { MetricNames } from "@/types/metric-names";

export const METRIC_NAMES_KEY = (projectId: string, runId: string) =>
  ["projects", projectId, "runs", runId, "metrics", "names"] as const;

export function useMetricNames({ projectId, runId }: { projectId: string; runId: string }) {
  return useQuery<MetricNames>({
    queryKey: METRIC_NAMES_KEY(projectId, runId),
    queryFn: () => fetchMetricNames({ projectId, runId }),
    enabled: Boolean(projectId) && Boolean(runId),
  });
}
