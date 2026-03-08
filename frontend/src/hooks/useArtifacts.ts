import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type { ArtifactType } from "@/types/artifact";
import { fetchArtifacts, deleteArtifact, cleanupArtifacts } from "@/api/artifacts";

const ARTIFACTS_KEY = (projectId: string, runId?: string, artifactType?: ArtifactType) =>
  ["projects", projectId, "artifacts", { runId, artifactType }] as const;

interface UseArtifactsParams {
  readonly projectId: string;
  readonly runId?: string;
  readonly artifactType?: ArtifactType;
}

export function useArtifacts({ projectId, runId, artifactType }: UseArtifactsParams) {
  return useQuery({
    queryKey: ARTIFACTS_KEY(projectId, runId, artifactType),
    queryFn: () => fetchArtifacts({ projectId, runId, artifactType }),
    enabled: Boolean(projectId),
  });
}

export function useDeleteArtifact() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ projectId, artifactId }: { projectId: string; artifactId: string }) =>
      deleteArtifact({ projectId, artifactId }),
    onSuccess: (_data, { projectId }) => {
      void queryClient.invalidateQueries({ queryKey: ["projects", projectId, "artifacts"] });
    },
  });
}

export function useCleanupArtifacts() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ projectId }: { projectId: string }) => cleanupArtifacts({ projectId }),
    onSuccess: (_data, { projectId }) => {
      void queryClient.invalidateQueries({ queryKey: ["projects", projectId, "artifacts"] });
      void queryClient.invalidateQueries({ queryKey: ["projects", projectId, "storage"] });
    },
  });
}
