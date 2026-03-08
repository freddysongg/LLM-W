import type { AppSettings, UpdateSettingsRequest, TestConnectionResult } from "@/types/settings";
import type { AIProvider } from "@/types/config";
import { fetchApi } from "./client";

interface RawAppSettings {
  readonly ai_provider: string;
  readonly ai_api_key_set: boolean;
  readonly ai_model_id: string;
  readonly ai_base_url: string | null;
  readonly default_projects_dir: string;
  readonly storage_warning_threshold_gb: number;
  readonly watchdog_stale_timeout_seconds: number;
  readonly watchdog_heartbeat_interval_seconds: number;
}

function normalizeAppSettings(raw: RawAppSettings): AppSettings {
  return {
    aiProvider: raw.ai_provider as AIProvider,
    isAiApiKeySet: raw.ai_api_key_set,
    aiModelId: raw.ai_model_id,
    aiBaseUrl: raw.ai_base_url,
    defaultProjectsDir: raw.default_projects_dir,
    storageWarningThresholdGb: raw.storage_warning_threshold_gb,
    watchdogStaleTimeoutSeconds: raw.watchdog_stale_timeout_seconds,
    watchdogHeartbeatIntervalSeconds: raw.watchdog_heartbeat_interval_seconds,
  };
}

export async function fetchSettings(): Promise<AppSettings> {
  const raw = await fetchApi<RawAppSettings>({ path: "/settings" });
  return normalizeAppSettings(raw);
}

export async function updateSettings({
  request,
}: {
  request: UpdateSettingsRequest;
}): Promise<AppSettings> {
  const raw = await fetchApi<RawAppSettings>({ path: "/settings", method: "PATCH", body: request });
  return normalizeAppSettings(raw);
}

export async function testAiConnection(): Promise<TestConnectionResult> {
  return fetchApi<TestConnectionResult>({ path: "/settings/ai/test", method: "POST" });
}
