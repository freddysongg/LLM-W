import type {
  LayerWeightStats,
  WeightSnapshotForLayer,
  WeightSnapshotsByLayer,
} from "@/types/weight-snapshot";
import { fetchApi } from "./client";

interface RawStats {
  readonly step: number;
  readonly mean: number;
  readonly std: number;
  readonly norm: number;
  readonly min_val: number;
  readonly max_val: number;
}

function toLayerStats(raw: RawStats): LayerWeightStats {
  return {
    step: raw.step,
    mean: raw.mean,
    std: raw.std,
    norm: raw.norm,
    minVal: raw.min_val,
    maxVal: raw.max_val,
  };
}

export async function fetchWeightSnapshotsAll({
  projectId,
  runId,
}: {
  projectId: string;
  runId: string;
}): Promise<WeightSnapshotsByLayer> {
  const raw = await fetchApi<{
    readonly run_id: string;
    readonly snapshots_by_layer: Readonly<Record<string, ReadonlyArray<RawStats>>>;
  }>({ path: `/projects/${projectId}/runs/${runId}/weight-snapshots` });
  const mapped: Record<string, ReadonlyArray<LayerWeightStats>> = {};
  for (const [name, points] of Object.entries(raw.snapshots_by_layer)) {
    mapped[name] = points.map(toLayerStats);
  }
  return { runId: raw.run_id, snapshotsByLayer: mapped };
}

export async function fetchWeightSnapshotsForLayer({
  projectId,
  runId,
  layerName,
}: {
  projectId: string;
  runId: string;
  layerName: string;
}): Promise<WeightSnapshotForLayer> {
  const raw = await fetchApi<{
    readonly run_id: string;
    readonly layer_name: string;
    readonly points: ReadonlyArray<RawStats>;
  }>({
    path: `/projects/${projectId}/runs/${runId}/weight-snapshots?layer=${encodeURIComponent(layerName)}`,
  });
  return {
    runId: raw.run_id,
    layerName: raw.layer_name,
    points: raw.points.map(toLayerStats),
  };
}
