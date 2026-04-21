export interface RunSummary {
  readonly runId: string;
  readonly status: string;
  readonly finalTrainLoss: number | null;
  readonly finalEvalLoss: number | null;
  readonly wallClockMs: number;
  readonly stepCount: number;
  readonly trainLossSparkline: ReadonlyArray<number>;
}
