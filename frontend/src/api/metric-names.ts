import type { MetricNames } from "@/types/metric-names";
import { fetchApi } from "./client";

interface RawMetricNames {
  readonly metric_names: ReadonlyArray<string>;
}

export async function fetchMetricNames({
  projectId,
  runId,
}: {
  projectId: string;
  runId: string;
}): Promise<MetricNames> {
  const raw = await fetchApi<RawMetricNames>({
    path: `/projects/${projectId}/runs/${runId}/metrics/names`,
  });
  return { metricNames: raw.metric_names };
}
