import type { RunSummary } from "@/types/run-summary";
import { fetchApi } from "./client";

interface RawRunSummary {
  readonly run_id: string;
  readonly status: string;
  readonly final_train_loss: number | null;
  readonly final_eval_loss: number | null;
  readonly wall_clock_ms: number;
  readonly step_count: number;
  readonly train_loss_sparkline: ReadonlyArray<number>;
}

interface RawRunSummariesResponse {
  readonly runs: ReadonlyArray<RawRunSummary>;
}

export async function fetchRunSummaries({
  projectId,
  runIds,
}: {
  projectId: string;
  runIds: ReadonlyArray<string>;
}): Promise<ReadonlyArray<RunSummary>> {
  if (runIds.length === 0) return [];
  const raw = await fetchApi<RawRunSummariesResponse>({
    path: `/projects/${projectId}/runs/summary?ids=${runIds.join(",")}`,
  });
  return raw.runs.map((summary) => ({
    runId: summary.run_id,
    status: summary.status,
    finalTrainLoss: summary.final_train_loss,
    finalEvalLoss: summary.final_eval_loss,
    wallClockMs: summary.wall_clock_ms,
    stepCount: summary.step_count,
    trainLossSparkline: summary.train_loss_sparkline,
  }));
}
