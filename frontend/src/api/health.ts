import type { HealthResponse, SystemHealthResponse } from "@/types/health";
import { fetchApi } from "./client";

interface RawSystemHealthResponse {
  readonly gpu_available: boolean;
  readonly gpu_name: string | null;
  readonly gpu_memory_total_mb: number | null;
  readonly gpu_memory_used_mb: number | null;
  readonly cpu_count: number;
  readonly ram_total_mb: number;
  readonly ram_used_mb: number;
  readonly disk_free_gb: number;
  readonly model_loaded: boolean;
  readonly active_run_id: string | null;
  readonly torch_device: string;
  readonly torch_version: string;
  readonly cuda_available: boolean;
  readonly mps_available: boolean;
}

function normalizeSystemHealth(raw: RawSystemHealthResponse): SystemHealthResponse {
  return {
    gpuAvailable: raw.gpu_available,
    gpuName: raw.gpu_name,
    gpuMemoryTotalMb: raw.gpu_memory_total_mb,
    gpuMemoryUsedMb: raw.gpu_memory_used_mb,
    cpuCount: raw.cpu_count,
    ramTotalMb: raw.ram_total_mb,
    ramUsedMb: raw.ram_used_mb,
    diskFreeGb: raw.disk_free_gb,
    isModelLoaded: raw.model_loaded,
    activeRunId: raw.active_run_id,
    torchDevice: raw.torch_device,
    torchVersion: raw.torch_version,
    isCudaAvailable: raw.cuda_available,
    isMpsAvailable: raw.mps_available,
  };
}

export async function fetchHealth(): Promise<HealthResponse> {
  return fetchApi<HealthResponse>({ path: "/health" });
}

export async function fetchSystemHealth(): Promise<SystemHealthResponse> {
  const raw = await fetchApi<RawSystemHealthResponse>({ path: "/health/system" });
  return normalizeSystemHealth(raw);
}
