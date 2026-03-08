import { useQuery } from "@tanstack/react-query";
import { fetchHealth, fetchSystemHealth } from "@/api/health";

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
