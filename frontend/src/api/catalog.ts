import type { ModalGpuOption } from "@/types/catalog";
import type { ModalGpuType } from "@/types/config";
import { ApiError, fetchApi } from "./client";

interface RawModalGpuOption {
  readonly gpu_type: string;
  readonly label: string;
  readonly vram_gb: number;
  readonly rate_usd_hr: number;
}

interface RawModalGpuCatalogResponse {
  readonly options: ReadonlyArray<RawModalGpuOption>;
}

const KNOWN_MODAL_GPU_TYPES: ReadonlySet<ModalGpuType> = new Set<ModalGpuType>([
  "t4",
  "a10",
  "l40s",
  "a100-40gb",
  "a100-80gb",
  "h100",
]);

function isModalGpuType(value: string): value is ModalGpuType {
  return KNOWN_MODAL_GPU_TYPES.has(value as ModalGpuType);
}

function normalizeOption(raw: RawModalGpuOption): ModalGpuOption {
  const { gpu_type, label, vram_gb, rate_usd_hr } = raw;
  if (!isModalGpuType(gpu_type)) {
    throw new ApiError({
      status: 200,
      statusText: "OK",
      code: "CATALOG_INVALID_GPU_TYPE",
      message: `Unknown modal_gpu_type received from server: ${gpu_type}`,
      details: { gpu_type },
    });
  }
  return {
    gpuType: gpu_type,
    label,
    vramGb: vram_gb,
    rateUsdHr: rate_usd_hr,
  };
}

export async function fetchModalGpus(): Promise<ReadonlyArray<ModalGpuOption>> {
  const raw = await fetchApi<RawModalGpuCatalogResponse>({ path: "/catalog/modal-gpus" });
  return raw.options.map(normalizeOption);
}
