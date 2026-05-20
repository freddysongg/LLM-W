import type { ModalGpuType } from "@/types/config";

export interface ModalGpuOption {
  readonly gpuType: ModalGpuType;
  readonly label: string;
  readonly vramGb: number;
  readonly rateUsdHr: number;
}
