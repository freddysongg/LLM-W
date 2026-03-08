import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchProjectStorage, cleanupProjectStorage } from "@/api/storage";

const STORAGE_KEY = (projectId: string) => ["projects", projectId, "storage"] as const;

export function useProjectStorage({ projectId }: { projectId: string }) {
  return useQuery({
    queryKey: STORAGE_KEY(projectId),
    queryFn: () => fetchProjectStorage({ projectId }),
    enabled: Boolean(projectId),
  });
}

export function useCleanupStorage() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ projectId }: { projectId: string }) => cleanupProjectStorage({ projectId }),
    onSuccess: (_data, { projectId }) => {
      void queryClient.invalidateQueries({ queryKey: STORAGE_KEY(projectId) });
      void queryClient.invalidateQueries({ queryKey: ["projects", projectId, "artifacts"] });
    },
  });
}
