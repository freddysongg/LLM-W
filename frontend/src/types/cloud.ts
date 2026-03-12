import type { ModalGpuType } from "./config";

export interface ModalTokenUpdate {
  readonly modalTokenId: string;
  readonly modalTokenSecret: string;
}

export interface ModalTestResponse {
  readonly success: boolean;
  readonly message: string;
}

export interface ModalGpuOption {
  readonly value: ModalGpuType;
  readonly label: string;
}

export const MODAL_GPU_OPTIONS: ReadonlyArray<ModalGpuOption> = [
  { value: "t4", label: "NVIDIA T4" },
  { value: "a10", label: "NVIDIA A10" },
  { value: "a100-40gb", label: "NVIDIA A100 40GB" },
  { value: "a100-80gb", label: "NVIDIA A100 80GB" },
  { value: "h100", label: "NVIDIA H100" },
] as const;
