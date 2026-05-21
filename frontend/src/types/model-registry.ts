export type RegisterModelSource = "hf" | "local" | "s3";
export type RegisterModelDtype = "bfloat16" | "float16" | "float32" | "int8" | "int4";

export interface ModelRegistryEntry {
  readonly name: string;
  readonly source: string;
  readonly isPinned: boolean;
  readonly params: string | null;
  readonly context: string | null;
  readonly license: string | null;
  readonly path: string | null;
  readonly dtype: string | null;
}

export interface RegisterModelEntryRequest {
  readonly name: string;
  readonly source: RegisterModelSource;
  readonly path: string;
  readonly dtype: RegisterModelDtype;
  readonly isPinned: boolean;
}
