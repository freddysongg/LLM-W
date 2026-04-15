import type { UseMutationResult, UseQueryResult } from "@tanstack/react-query";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createEvalRun,
  fetchEvalRun,
  fetchEvalRunCalls,
  fetchEvalRuns,
  fetchRubrics,
} from "@/api/eval";
import { InvariantError } from "@/lib/errors";
import type {
  EvalCallsPage,
  EvalListQuery,
  EvalRun,
  EvalRunCreateRequest,
  EvalRunDetail,
  Rubric,
} from "@/types/eval";

const EVAL_RUNS_KEY = (trainingRunId: string | null | undefined) =>
  ["eval", "runs", trainingRunId ?? null] as const;
const EVAL_RUN_KEY = (evalRunId: string) => ["eval", "runs", "detail", evalRunId] as const;
const EVAL_RUN_CALLS_KEY = (
  evalRunId: string,
  limit: number | undefined,
  offset: number | undefined,
) => ["eval", "runs", "calls", evalRunId, limit ?? null, offset ?? null] as const;
const RUBRICS_KEY = ["eval", "rubrics"] as const;

const EVAL_RUNS_REFETCH_INTERVAL_MS = 5000;

export function useEvalRuns(
  params: EvalListQuery = {},
): UseQueryResult<ReadonlyArray<EvalRun>, Error> {
  return useQuery({
    queryKey: EVAL_RUNS_KEY(params.trainingRunId ?? null),
    queryFn: () => fetchEvalRuns(params),
    refetchInterval: EVAL_RUNS_REFETCH_INTERVAL_MS,
  });
}

export function useEvalRun({
  evalRunId,
}: {
  evalRunId: string | null;
}): UseQueryResult<EvalRunDetail, Error> {
  return useQuery({
    queryKey: EVAL_RUN_KEY(evalRunId ?? ""),
    queryFn: () => {
      if (!evalRunId) {
        throw new InvariantError("evalRunId is required");
      }
      return fetchEvalRun({ evalRunId });
    },
    enabled: Boolean(evalRunId),
  });
}

export function useEvalRunCalls({
  evalRunId,
  limit,
  offset,
}: {
  evalRunId: string | null;
  limit?: number;
  offset?: number;
}): UseQueryResult<EvalCallsPage, Error> {
  return useQuery({
    queryKey: EVAL_RUN_CALLS_KEY(evalRunId ?? "", limit, offset),
    queryFn: () => {
      if (!evalRunId) {
        throw new InvariantError("evalRunId is required");
      }
      return fetchEvalRunCalls({ evalRunId, limit, offset });
    },
    enabled: Boolean(evalRunId),
  });
}

export function useRubrics(): UseQueryResult<ReadonlyArray<Rubric>, Error> {
  return useQuery({
    queryKey: RUBRICS_KEY,
    queryFn: fetchRubrics,
  });
}

export function useCreateEvalRun(): UseMutationResult<EvalRun, Error, EvalRunCreateRequest> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (request: EvalRunCreateRequest) => createEvalRun(request),
    onSuccess: (createdRun) => {
      void queryClient.invalidateQueries({
        queryKey: EVAL_RUNS_KEY(createdRun.trainingRunId ?? null),
      });
      void queryClient.invalidateQueries({ queryKey: EVAL_RUNS_KEY(null) });
    },
  });
}

export function invalidateEvalRunQueries({
  queryClient,
  evalRunId,
}: {
  queryClient: ReturnType<typeof useQueryClient>;
  evalRunId: string;
}): void {
  void queryClient.invalidateQueries({ queryKey: EVAL_RUN_KEY(evalRunId) });
  void queryClient.invalidateQueries({ queryKey: ["eval", "runs", "calls", evalRunId] });
  void queryClient.invalidateQueries({ queryKey: ["eval", "runs"] });
}
