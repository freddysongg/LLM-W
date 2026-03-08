export interface HealthResponse {
  readonly status: "ok";
  readonly version: string;
}

export interface SystemHealthResponse {
  readonly gpuAvailable: boolean;
  readonly gpuName: string | null;
  readonly gpuMemoryTotalMb: number | null;
  readonly gpuMemoryUsedMb: number | null;
  readonly cpuCount: number;
  readonly ramTotalMb: number;
  readonly ramUsedMb: number;
  readonly diskFreeGb: number;
  readonly isModelLoaded: boolean;
  readonly activeRunId: string | null;
  readonly torchDevice: string;
  readonly torchVersion: string;
  readonly isCudaAvailable: boolean;
  readonly isMpsAvailable: boolean;
}
