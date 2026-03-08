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
