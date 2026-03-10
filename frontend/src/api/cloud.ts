import type { ModalGpuType } from "@/types/run";
import { fetchApi } from "./client";

export interface ModalGpuOption {
  readonly value: ModalGpuType;
  readonly label: string;
  readonly vramGb: number;
  readonly pricePerHour: number;
}

export const MODAL_GPU_OPTIONS: ReadonlyArray<ModalGpuOption> = [
  { value: "t4", label: "T4 16GB", vramGb: 16, pricePerHour: 0.59 },
  { value: "a10", label: "A10 24GB", vramGb: 24, pricePerHour: 1.1 },
  { value: "a100-40gb", label: "A100 40GB", vramGb: 40, pricePerHour: 2.1 },
  { value: "a100-80gb", label: "A100 80GB", vramGb: 80, pricePerHour: 2.5 },
  { value: "h100", label: "H100 80GB", vramGb: 80, pricePerHour: 3.95 },
] as const;

export interface ModalTestResult {
  readonly success: boolean;
  readonly message: string;
}

export async function testModalToken(): Promise<ModalTestResult> {
  return fetchApi<ModalTestResult>({ path: "/settings/modal/test", method: "POST" });
}
