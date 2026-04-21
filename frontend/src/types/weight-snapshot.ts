export interface LayerWeightStats {
  readonly step: number;
  readonly mean: number;
  readonly std: number;
  readonly norm: number;
  readonly minVal: number;
  readonly maxVal: number;
}

export interface WeightSnapshotsByLayer {
  readonly runId: string;
  readonly snapshotsByLayer: Readonly<Record<string, ReadonlyArray<LayerWeightStats>>>;
}

export interface WeightSnapshotForLayer {
  readonly runId: string;
  readonly layerName: string;
  readonly points: ReadonlyArray<LayerWeightStats>;
}
