import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchRuns,
  fetchRun,
  createRun,
  deleteRun,
  cancelRun,
  pauseRun,
  resumeRun,
  fetchRunStages,
  fetchRunMetrics,
  fetchRunLogs,
  fetchCheckpoints,
} from "@/api/runs";
import type { MetricsParams, LogsParams } from "@/types/run";

const RUNS_KEY = (projectId: string) => ["projects", projectId, "runs"] as const;
const RUN_KEY = (projectId: string, runId: string) =>
  ["projects", projectId, "runs", runId] as const;

export function useRuns({ projectId }: { projectId: string }) {
  return useQuery({
    queryKey: RUNS_KEY(projectId),
    queryFn: () => fetchRuns({ projectId }),
    enabled: Boolean(projectId),
    refetchInterval: 5000,
  });
}

export function useRun({ projectId, runId }: { projectId: string; runId: string }) {
  return useQuery({
    queryKey: RUN_KEY(projectId, runId),
    queryFn: () => fetchRun({ projectId, runId }),
    enabled: Boolean(projectId) && Boolean(runId),
  });
}

export function useCreateRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ projectId, configVersionId }: { projectId: string; configVersionId: string }) =>
      createRun({ projectId, configVersionId }),
    onSuccess: (_data, { projectId }) => {
      void queryClient.invalidateQueries({ queryKey: RUNS_KEY(projectId) });
    },
  });
}

export function useDeleteRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ projectId, runId }: { projectId: string; runId: string }) =>
      deleteRun({ projectId, runId }),
    onSuccess: (_data, { projectId }) => {
      void queryClient.invalidateQueries({ queryKey: RUNS_KEY(projectId) });
    },
  });
}

export function useCancelRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ projectId, runId }: { projectId: string; runId: string }) =>
      cancelRun({ projectId, runId }),
    onSuccess: (_data, { projectId, runId }) => {
      void queryClient.invalidateQueries({ queryKey: RUN_KEY(projectId, runId) });
      void queryClient.invalidateQueries({ queryKey: RUNS_KEY(projectId) });
    },
  });
}

export function usePauseRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ projectId, runId }: { projectId: string; runId: string }) =>
      pauseRun({ projectId, runId }),
    onSuccess: (_data, { projectId, runId }) => {
      void queryClient.invalidateQueries({ queryKey: RUN_KEY(projectId, runId) });
      void queryClient.invalidateQueries({ queryKey: RUNS_KEY(projectId) });
    },
  });
}

export function useResumeRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ projectId, runId }: { projectId: string; runId: string }) =>
      resumeRun({ projectId, runId }),
    onSuccess: (_data, { projectId }) => {
      void queryClient.invalidateQueries({ queryKey: RUNS_KEY(projectId) });
    },
  });
}

export function useRunStages({ projectId, runId }: { projectId: string; runId: string }) {
  return useQuery({
    queryKey: [...RUN_KEY(projectId, runId), "stages"],
    queryFn: () => fetchRunStages({ projectId, runId }),
    enabled: Boolean(projectId) && Boolean(runId),
  });
}

export function useRunMetrics({
  projectId,
  runId,
  params,
}: {
  projectId: string;
  runId: string;
  params?: MetricsParams;
}) {
  return useQuery({
    queryKey: [...RUN_KEY(projectId, runId), "metrics", params],
    queryFn: () => fetchRunMetrics({ projectId, runId, params }),
    enabled: Boolean(projectId) && Boolean(runId),
  });
}

export function useRunLogs({
  projectId,
  runId,
  params,
}: {
  projectId: string;
  runId: string;
  params?: LogsParams;
}) {
  return useQuery({
    queryKey: [...RUN_KEY(projectId, runId), "logs", params],
    queryFn: () => fetchRunLogs({ projectId, runId, params }),
    enabled: Boolean(projectId) && Boolean(runId),
  });
}

export function useCheckpoints({ projectId, runId }: { projectId: string; runId: string }) {
  return useQuery({
    queryKey: [...RUN_KEY(projectId, runId), "checkpoints"],
    queryFn: () => fetchCheckpoints({ projectId, runId }),
    enabled: Boolean(projectId) && Boolean(runId),
  });
}
