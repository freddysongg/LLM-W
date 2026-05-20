import type { Notification } from "@/types/notification";
import { fetchApi } from "./client";

interface RawNotification {
  readonly id: string;
  readonly type: string;
  readonly title: string;
  readonly subtitle: string | null;
  readonly created_at: string;
  readonly read_at: string | null;
}

interface RawNotificationListResponse {
  readonly items: ReadonlyArray<RawNotification>;
}

function normalizeNotification(raw: RawNotification): Notification {
  return {
    id: raw.id,
    type: raw.type,
    title: raw.title,
    subtitle: raw.subtitle,
    createdAt: raw.created_at,
    readAt: raw.read_at,
  };
}

export async function fetchNotifications(): Promise<ReadonlyArray<Notification>> {
  const raw = await fetchApi<RawNotificationListResponse>({ path: "/notifications" });
  return raw.items.map(normalizeNotification);
}

export async function markNotificationRead({ id }: { id: string }): Promise<Notification> {
  const raw = await fetchApi<RawNotification>({
    path: `/notifications/${id}/read`,
    method: "POST",
  });
  return normalizeNotification(raw);
}
