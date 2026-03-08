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

// -- Architecture (matches backend LayerNode / ModelArchitectureResponse) --

export interface LayerNode {
  readonly name: string;
  readonly type: string;
  readonly params: number | null;
  readonly trainable: boolean | null;
  readonly dtype: string | null;
  readonly shape: ReadonlyArray<number> | null;
  readonly children: ReadonlyArray<LayerNode> | null;
}

export interface ModelArchitectureResponse {
  readonly model_id: string;
  readonly architecture_name: string;
  readonly total_parameters: number;
  readonly trainable_parameters: number;
  readonly tree: LayerNode;
}

// -- Layer Detail (matches backend LayerDetailResponse) --

export interface LayerDetailResponse {
  readonly name: string;
  readonly type: string;
  readonly params: number;
  readonly trainable: boolean;
  readonly dtype: string | null;
  readonly shape: ReadonlyArray<number> | null;
}

// -- Activations (matches backend schemas) --

export interface TierOneStats {
  readonly mean: number;
  readonly std: number;
  readonly min: number;
  readonly max: number;
  readonly histogram_bins: ReadonlyArray<number>;
}

export interface ActivationLayerSnapshot {
  readonly layer_name: string;
  readonly tier1: TierOneStats;
  readonly shape: ReadonlyArray<number>;
}

export interface ActivationSnapshotResponse {
  readonly id: string;
  readonly created_at: string;
  readonly layers: ReadonlyArray<ActivationLayerSnapshot>;
}

export interface ActivationCaptureRequest {
  readonly layer_names: ReadonlyArray<string>;
  readonly sample_input: string;
}

export interface FullTensorRequest {
  readonly layer_names: ReadonlyArray<string> | null;
}

export interface FullTensorResponse {
  readonly snapshot_id: string;
  readonly layer_tensors: Record<string, unknown>;
}

// -- UI-only computed types --

export interface WeightDelta {
  readonly layerName: string;
  readonly deltaMagnitude: number;
  readonly meanBefore: number;
  readonly meanAfter: number;
  readonly stdBefore: number;
  readonly stdAfter: number;
}

export interface ParameterRow {
  readonly path: string;
  readonly type: string;
  readonly params: number;
  readonly trainable: boolean | null;
  readonly dtype: string | null;
}
