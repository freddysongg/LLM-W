import { useQuery, useQueries } from "@tanstack/react-query";
import { fetchRunComparison, fetchRunMetrics } from "@/api/runs";
import type { RunCompareResponse, MetricPoint } from "@/types/run";

const COMPARE_KEY = (projectId: string, runIds: ReadonlyArray<string>) =>
  ["projects", projectId, "runs", "compare", [...runIds].sort()] as const;

const METRICS_KEY = (projectId: string, runId: string) =>
  ["projects", projectId, "runs", runId, "metrics"] as const;

interface UseRunComparisonResult {
  readonly compareData: RunCompareResponse | undefined;
  readonly runMetrics: Record<string, ReadonlyArray<MetricPoint>>;
  readonly isLoading: boolean;
  readonly error: Error | null;
}

export function useRunComparison({
  projectId,
  runIds,
}: {
  projectId: string;
  runIds: ReadonlyArray<string>;
}): UseRunComparisonResult {
  const isEnabled = Boolean(projectId) && runIds.length >= 2;

  const comparisonQuery = useQuery({
    queryKey: COMPARE_KEY(projectId, runIds),
    queryFn: () => fetchRunComparison({ projectId, runIds }),
    enabled: isEnabled,
  });

  const metricsQueries = useQueries({
    queries: runIds.map((runId) => ({
      queryKey: METRICS_KEY(projectId, runId),
      queryFn: () => fetchRunMetrics({ projectId, runId }),
      enabled: isEnabled,
    })),
  });

  const runMetrics: Record<string, ReadonlyArray<MetricPoint>> = Object.fromEntries(
    runIds.map((runId, i) => [runId, metricsQueries[i]?.data ?? []]),
  );

  const metricsError = metricsQueries.find((q) => q.error)?.error ?? null;

  return {
    compareData: comparisonQuery.data,
    runMetrics,
    isLoading: comparisonQuery.isLoading || metricsQueries.some((q) => q.isLoading),
    error: comparisonQuery.error ?? metricsError,
  };
}
