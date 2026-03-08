import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type { ModelResolveRequest } from "@/types/model";
import { resolveModel, fetchModelProfile, fetchModelArchitecture } from "@/api/models";

const modelQueryKey = (projectId: string) => ["projects", projectId, "models"] as const;

export function useModelProfile({ projectId }: { projectId: string }) {
  return useQuery({
    queryKey: [...modelQueryKey(projectId), "profile"],
    queryFn: () => fetchModelProfile({ projectId }),
    enabled: Boolean(projectId),
    retry: (failureCount, error: unknown) => {
      if (
        error instanceof Error &&
        "status" in error &&
        (error as { status: number }).status === 404
      ) {
        return false;
      }
      return failureCount < 1;
    },
  });
}

export function useModelArchitecture({ projectId }: { projectId: string }) {
  return useQuery({
    queryKey: [...modelQueryKey(projectId), "architecture"],
    queryFn: () => fetchModelArchitecture({ projectId }),
    enabled: Boolean(projectId),
    retry: (failureCount, error: unknown) => {
      if (
        error instanceof Error &&
        "status" in error &&
        (error as { status: number }).status === 404
      ) {
        return false;
      }
      return failureCount < 1;
    },
  });
}

export function useResolveModel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ projectId, request }: { projectId: string; request: ModelResolveRequest }) =>
      resolveModel({ projectId, request }),
    onSuccess: (_, { projectId }) => {
      void queryClient.invalidateQueries({ queryKey: modelQueryKey(projectId) });
    },
  });
}
