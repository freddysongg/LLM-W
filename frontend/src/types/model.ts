import type { ModelFamily, ModelSource } from "./config";

export interface ModelCapabilities {
  readonly supportedTasks: ReadonlyArray<string>;
  readonly supportedAdapters: ReadonlyArray<string>;
  readonly supportedQuantModes: ReadonlyArray<string>;
}

export interface ResourceEstimate {
  readonly vramMb: number;
  readonly ramMb: number;
  readonly diskMb: number;
}

export interface ModelProfile {
  readonly id: string;
  readonly projectId: string;
  readonly source: ModelSource;
  readonly modelId: string;
  readonly family: ModelFamily;
  readonly architectureName: string | null;
  readonly parameterCount: number | null;
  readonly trainableCount: number | null;
  readonly tokenizerType: string | null;
  readonly vocabSize: number | null;
  readonly maxPositionEmbeddings: number | null;
  readonly hiddenSize: number | null;
  readonly numLayers: number | null;
  readonly numAttentionHeads: number | null;
  readonly capabilities: ModelCapabilities | null;
  readonly resourceEstimate: ResourceEstimate | null;
  readonly createdAt: string;
  readonly updatedAt: string;
}

export interface ArchitectureNode {
  readonly name: string;
  readonly type: string;
  readonly paramCount: number;
  readonly isTrainable: boolean;
  readonly children: ReadonlyArray<ArchitectureNode>;
}

export interface LayerDetail {
  readonly name: string;
  readonly type: string;
  readonly paramCount: number;
  readonly dtype: string;
  readonly shape: ReadonlyArray<number>;
  readonly isTrainable: boolean;
  readonly hasAdapter: boolean;
}

export interface ActivationSummary {
  readonly mean: number;
  readonly std: number;
  readonly min: number;
  readonly max: number;
  readonly histogramBins: ReadonlyArray<number>;
  readonly histogramCounts: ReadonlyArray<number>;
}

export interface ActivationSnapshot {
  readonly id: string;
  readonly runId: string;
  readonly checkpointStep: number;
  readonly layerName: string;
  readonly summary: ActivationSummary;
  readonly fullTensorPath: string | null;
  readonly sampleInputHash: string | null;
  readonly createdAt: string;
}
