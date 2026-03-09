export interface FlowNode {
  readonly fullPath: string;
  readonly name: string;
  readonly depth: number;
  readonly isGroupHeader: boolean;
  readonly type: string;
  readonly params: number | null;
  readonly shape: ReadonlyArray<number> | null;
  readonly trainable: boolean | null;
}

export interface FlowColumn {
  readonly key: string;
  readonly label: string;
  readonly totalParams: number;
  readonly nodes: ReadonlyArray<FlowNode>;
  readonly isRepeated: boolean;
  readonly repeatCount: number;
}

export type FlowMode = "structural" | "activation";

export interface FlowActivationCell {
  readonly tokenString: string;
  readonly layerName: string;
  readonly mean: number;
  readonly std: number;
  readonly min: number;
  readonly max: number;
}

export interface TokenRow {
  readonly tokenString: string;
  readonly position: number;
}
