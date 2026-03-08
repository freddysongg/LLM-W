import { useQuery, useMutation } from "@tanstack/react-query";
import { fetchDatasetSamples, previewTransform } from "@/api/datasets";
import type { PreviewTransformRequest } from "@/types/dataset";

const SAMPLES_KEY = (projectId: string, limit: number, offset: number) =>
  ["projects", projectId, "dataset", "samples", { limit, offset }] as const;

const PREVIEW_KEY = (projectId: string) => ["projects", projectId, "dataset", "preview"] as const;

export function useDatasetSamples({
  projectId,
  limit = 20,
  offset = 0,
  enabled = true,
}: {
  projectId: string;
  limit?: number;
  offset?: number;
  enabled?: boolean;
}) {
  return useQuery({
    queryKey: SAMPLES_KEY(projectId, limit, offset),
    queryFn: () => fetchDatasetSamples({ projectId, limit, offset }),
    enabled: Boolean(projectId) && enabled,
    retry: false,
  });
}

export function usePreviewTransform({ projectId }: { projectId: string }) {
  return useMutation({
    mutationKey: PREVIEW_KEY(projectId),
    mutationFn: (request: PreviewTransformRequest) => previewTransform({ projectId, request }),
  });
}
