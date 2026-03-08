import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type { UpdateSettingsRequest } from "@/types/settings";
import { fetchSettings, updateSettings, testAiConnection } from "@/api/settings";

const SETTINGS_QUERY_KEY = ["settings"] as const;

export function useSettings() {
  return useQuery({
    queryKey: SETTINGS_QUERY_KEY,
    queryFn: fetchSettings,
  });
}

export function useUpdateSettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ request }: { request: UpdateSettingsRequest }) => updateSettings({ request }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: SETTINGS_QUERY_KEY });
    },
  });
}

export function useTestAiConnection() {
  return useMutation({
    mutationFn: testAiConnection,
  });
}
