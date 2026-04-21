import type { RunLayerProfile, RunModelProfile } from "@/types/run-model-profile";
import { fetchApi } from "./client";

interface RawLayer {
  readonly name: string;
  readonly shape: ReadonlyArray<number>;
  readonly param_count: number;
  readonly trainable: boolean;
  readonly dtype: string;
}

interface RawRunModelProfile {
  readonly run_id: string;
  readonly total_params: number;
  readonly trainable_params: number;
  readonly layers: ReadonlyArray<RawLayer>;
}

export async function fetchRunModelProfile({
  projectId,
  runId,
}: {
  projectId: string;
  runId: string;
}): Promise<RunModelProfile> {
  const raw = await fetchApi<RawRunModelProfile>({
    path: `/projects/${projectId}/runs/${runId}/model-profile`,
  });
  return {
    runId: raw.run_id,
    totalParams: raw.total_params,
    trainableParams: raw.trainable_params,
    layers: raw.layers.map(
      (r): RunLayerProfile => ({
        name: r.name,
        shape: r.shape,
        paramCount: r.param_count,
        trainable: r.trainable,
        dtype: r.dtype,
      }),
    ),
  };
}
