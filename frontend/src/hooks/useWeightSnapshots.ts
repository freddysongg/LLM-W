import { useQuery } from "@tanstack/react-query";

import { fetchWeightSnapshotsAll, fetchWeightSnapshotsForLayer } from "@/api/weight-snapshots";
import type { WeightSnapshotForLayer, WeightSnapshotsByLayer } from "@/types/weight-snapshot";

export function useWeightSnapshotsAll({ projectId, runId }: { projectId: string; runId: string }) {
  return useQuery<WeightSnapshotsByLayer>({
    queryKey: ["projects", projectId, "runs", runId, "weight-snapshots", "all"],
    queryFn: () => fetchWeightSnapshotsAll({ projectId, runId }),
    enabled: Boolean(projectId) && Boolean(runId),
  });
}

export function useWeightSnapshotsForLayer({
  projectId,
  runId,
  layerName,
}: {
  projectId: string;
  runId: string;
  layerName: string | null;
}) {
  return useQuery<WeightSnapshotForLayer>({
    queryKey: ["projects", projectId, "runs", runId, "weight-snapshots", layerName],
    queryFn: () => {
      if (layerName === null) {
        throw new Error("layerName required");
      }
      return fetchWeightSnapshotsForLayer({ projectId, runId, layerName });
    },
    enabled: Boolean(projectId) && Boolean(runId) && layerName !== null,
  });
}
