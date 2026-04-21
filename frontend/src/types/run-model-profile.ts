export interface RunLayerProfile {
  readonly name: string;
  readonly shape: ReadonlyArray<number>;
  readonly paramCount: number;
  readonly trainable: boolean;
  readonly dtype: string;
}

export interface RunModelProfile {
  readonly runId: string;
  readonly totalParams: number;
  readonly trainableParams: number;
  readonly layers: ReadonlyArray<RunLayerProfile>;
}
