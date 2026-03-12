import type { AIProvider } from "./config";

export interface AppSettings {
  readonly aiProvider: AIProvider;
  readonly isAiApiKeySet: boolean;
  readonly aiModelId: string;
  readonly aiBaseUrl: string | null;
  readonly defaultProjectsDir: string;
  readonly storageWarningThresholdGb: number;
  readonly watchdogStaleTimeoutSeconds: number;
  readonly watchdogHeartbeatIntervalSeconds: number;
  readonly isModalTokenSet: boolean;
}

export interface UpdateSettingsRequest {
  readonly aiProvider?: AIProvider;
  readonly aiApiKey?: string;
  readonly aiModelId?: string;
  readonly aiBaseUrl?: string;
  readonly defaultProjectsDir?: string;
  readonly storageWarningThresholdGb?: number;
  readonly watchdogStaleTimeoutSeconds?: number;
  readonly watchdogHeartbeatIntervalSeconds?: number;
  readonly modalTokenId?: string;
  readonly modalTokenSecret?: string;
}

export interface TestConnectionResult {
  readonly success: boolean;
  readonly message: string;
}

export interface ApiKeySaveResult {
  readonly success: boolean;
}
