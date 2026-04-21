import { useQuery } from "@tanstack/react-query";

import { fetchRunModelProfile } from "@/api/run-model-profile";
import type { RunModelProfile } from "@/types/run-model-profile";

export function useRunModelProfile({ projectId, runId }: { projectId: string; runId: string }) {
  return useQuery<RunModelProfile>({
    queryKey: ["projects", projectId, "runs", runId, "model-profile"],
    queryFn: () => fetchRunModelProfile({ projectId, runId }),
    enabled: Boolean(projectId) && Boolean(runId),
  });
}
