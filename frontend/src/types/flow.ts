export interface FlowNode {
  readonly fullPath: string;
  readonly name: string;
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
