import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createMergedModel, deleteMergedModel, fetchMergedModels } from "@/api/merged-models";
import type { MergeRunRequest } from "@/types/merged-model";

const MERGED_MODELS_KEY = (projectId: string) => ["projects", projectId, "merged-models"] as const;

export function useMergedModels({ projectId }: { projectId: string }) {
  return useQuery({
    queryKey: MERGED_MODELS_KEY(projectId),
    queryFn: () => fetchMergedModels({ projectId }),
    enabled: Boolean(projectId),
  });
}

export function useCreateMergedModel({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (request: MergeRunRequest) => createMergedModel({ projectId, request }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: MERGED_MODELS_KEY(projectId) });
    },
  });
}

export function useDeleteMergedModel({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (mergedId: string) => deleteMergedModel({ projectId, mergedId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: MERGED_MODELS_KEY(projectId) });
    },
  });
}
