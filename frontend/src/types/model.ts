import type { ModelSource } from "./config";

export type { ModelSource };

export interface ModelResolveRequest {
  readonly source: ModelSource;
  readonly model_id: string;
  readonly revision?: string;
  readonly trust_remote_code?: boolean;
}

export interface ResourceEstimate {
  readonly vram_gb: number;
  readonly disk_gb: number;
  readonly training_memory_gb: number;
}

export interface ModelProfile {
  readonly model_id: string;
  readonly source: ModelSource;
  readonly family: string;
  readonly architecture_name: string;
  readonly total_parameters: number;
  readonly trainable_parameters: number;
  readonly resource_estimate: ResourceEstimate;
  readonly torch_dtype: string;
  readonly vocabulary_size: number | null;
  readonly context_length: number | null;
  readonly resolved_at: string;
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
