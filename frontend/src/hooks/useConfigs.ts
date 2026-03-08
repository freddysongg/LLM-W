import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type { SaveConfigRequest } from "@/types/config";
import { fetchActiveConfig, saveConfig } from "@/api/configs";

const CONFIG_KEY = (projectId: string) => ["projects", projectId, "configs", "active"] as const;

export function useActiveConfig({ projectId }: { projectId: string }) {
  return useQuery({
    queryKey: CONFIG_KEY(projectId),
    queryFn: () => fetchActiveConfig({ projectId }),
    enabled: Boolean(projectId),
  });
}

export function useSaveConfig({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ request }: { request: SaveConfigRequest }) => saveConfig({ projectId, request }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: CONFIG_KEY(projectId) });
    },
  });
}
