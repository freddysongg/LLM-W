import { useQuery } from "@tanstack/react-query";
import { fetchModelArchitecture, fetchLayerDetail } from "@/api/model-explorer";

const ARCHITECTURE_KEY = (projectId: string) => ["projects", projectId, "architecture"] as const;

const LAYER_DETAIL_KEY = (projectId: string, layerName: string) =>
  ["projects", projectId, "layers", layerName] as const;

export function useModelArchitecture({ projectId }: { projectId: string }) {
  return useQuery({
    queryKey: ARCHITECTURE_KEY(projectId),
    queryFn: () => fetchModelArchitecture({ projectId }),
    enabled: Boolean(projectId),
    // Architecture is static for a given resolved model — never mark stale to avoid
    // redundant refetches on window focus while the backend computes it
    staleTime: Infinity,
  });
}

export function useLayerDetail({
  projectId,
  layerName,
}: {
  projectId: string;
  layerName: string | null;
}) {
  return useQuery({
    queryKey: LAYER_DETAIL_KEY(projectId, layerName ?? ""),
    queryFn: () => fetchLayerDetail({ projectId, layerName: layerName! }),
    enabled: Boolean(projectId) && Boolean(layerName),
  });
}
