import { useQuery } from "@tanstack/react-query";
import type { HealthResponse, SystemHealthResponse } from "@/types/health";
import { fetchApi } from "@/api/client";

async function fetchHealth(): Promise<HealthResponse> {
  return fetchApi<HealthResponse>({ path: "/health" });
}

async function fetchSystemHealth(): Promise<SystemHealthResponse> {
  return fetchApi<SystemHealthResponse>({ path: "/health/system" });
}

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    refetchInterval: 30_000,
  });
}

export function useSystemHealth() {
  return useQuery({
    queryKey: ["health", "system"],
    queryFn: fetchSystemHealth,
    refetchInterval: 10_000,
  });
}
