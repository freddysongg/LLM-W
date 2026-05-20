import { useMutation, useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";

import { fetchNotifications, markNotificationRead } from "@/api/notifications";
import type { Notification } from "@/types/notification";

const NOTIFICATIONS_KEY = ["notifications"] as const;
const NOTIFICATIONS_REFRESH_INTERVAL_MS: number = 30 * 1000;

export function useNotifications(): UseQueryResult<ReadonlyArray<Notification>, Error> {
  return useQuery({
    queryKey: NOTIFICATIONS_KEY,
    queryFn: fetchNotifications,
    refetchInterval: NOTIFICATIONS_REFRESH_INTERVAL_MS,
  });
}

export function useMarkNotificationRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id }: { id: string }) => markNotificationRead({ id }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: NOTIFICATIONS_KEY });
    },
  });
}
