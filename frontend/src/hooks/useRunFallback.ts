import { useMutation, useQueryClient, type UseMutationResult } from "@tanstack/react-query";

import { postRunFallback, type RunFallbackBody } from "@/api/runs";
import type { Run } from "@/types/run";

export function useRunFallback({
  projectId,
  runId,
}: {
  projectId: string;
  runId: string;
}): UseMutationResult<Run, Error, RunFallbackBody> {
  const queryClient = useQueryClient();
  return useMutation<Run, Error, RunFallbackBody>({
    mutationFn: (body: RunFallbackBody) => postRunFallback({ projectId, runId, body }),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["projects", projectId, "runs", runId],
      });
      void queryClient.invalidateQueries({
        queryKey: ["projects", projectId, "runs"],
      });
    },
  });
}
