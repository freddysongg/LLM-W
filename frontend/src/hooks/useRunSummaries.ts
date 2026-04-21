import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { fetchRunSummaries } from "@/api/run-summary";
import type { RunSummary } from "@/types/run-summary";

export function useRunSummaries({
  projectId,
  runIds,
}: {
  projectId: string;
  runIds: ReadonlyArray<string>;
}): UseQueryResult<ReadonlyArray<RunSummary>> {
  return useQuery<ReadonlyArray<RunSummary>>({
    queryKey: ["projects", projectId, "runs", "summary", [...runIds]],
    queryFn: () => fetchRunSummaries({ projectId, runIds }),
    enabled: Boolean(projectId) && runIds.length > 0,
  });
}
