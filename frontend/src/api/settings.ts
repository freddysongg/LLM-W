import type { AppSettings, UpdateSettingsRequest } from "@/types/settings";
import { fetchApi } from "./client";

interface TestConnectionResult {
  readonly success: boolean;
  readonly message: string;
}

export async function fetchSettings(): Promise<AppSettings> {
  return fetchApi<AppSettings>({ path: "/settings" });
}

export async function updateSettings({
  request,
}: {
  request: UpdateSettingsRequest;
}): Promise<AppSettings> {
  return fetchApi<AppSettings>({ path: "/settings", method: "PATCH", body: request });
}

export async function testAiConnection(): Promise<TestConnectionResult> {
  return fetchApi<TestConnectionResult>({ path: "/settings/ai/test", method: "POST" });
}
