import * as React from "react";
import { useState, useEffect, useMemo } from "react";
import type { AppSettings, UpdateSettingsRequest, ApiKeySaveResult } from "@/types/settings";
import type { AIProvider } from "@/types/config";
import type { LlmCatalogProvider, LlmModelOption } from "@/types/llm-catalog";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Check } from "lucide-react";
import { useLlmModels } from "@/hooks/useCatalog";

const PROVIDER_DEFAULT_MODEL_ID: Readonly<Record<LlmCatalogProvider, string>> = {
  openai: "gpt-4o",
  anthropic: "claude-sonnet-4-6",
};

interface SettingsFormProps {
  readonly settings: AppSettings;
  readonly onSave: (updates: UpdateSettingsRequest) => void;
  readonly onSetApiKey: (apiKey: string) => void;
  readonly isSavingApiKey: boolean;
  readonly apiKeySaveResult: ApiKeySaveResult | null;
  readonly onTestConnection: () => void;
  readonly isTestingConnection: boolean;
  readonly testConnectionResult: { readonly success: boolean; readonly message: string } | null;
  readonly onSetModalToken: (credentials: { tokenId: string; tokenSecret: string }) => void;
  readonly isSavingModalToken: boolean;
  readonly modalTokenSaveResult: ApiKeySaveResult | null;
  readonly onTestModalConnection: () => void;
  readonly isTestingModalConnection: boolean;
  readonly modalTestResult: { readonly success: boolean; readonly message: string } | null;
}

export function SettingsForm({
  settings,
  onSave,
  onSetApiKey,
  isSavingApiKey,
  apiKeySaveResult,
  onTestConnection,
  isTestingConnection,
  testConnectionResult,
  onSetModalToken,
  isSavingModalToken,
  modalTokenSaveResult,
  onTestModalConnection,
  isTestingModalConnection,
  modalTestResult,
}: SettingsFormProps): React.JSX.Element {
  const [aiProvider, setAiProvider] = useState<AIProvider>(settings.aiProvider);
  const [aiApiKey, setAiApiKey] = useState("");
  const [aiModelId, setAiModelId] = useState(settings.aiModelId);
  const [aiBaseUrl, setAiBaseUrl] = useState(settings.aiBaseUrl ?? "");
  const [defaultProjectsDir, setDefaultProjectsDir] = useState(settings.defaultProjectsDir);
  const [storageWarningThresholdGb, setStorageWarningThresholdGb] = useState(
    String(settings.storageWarningThresholdGb),
  );
  const [watchdogStaleTimeoutSeconds, setWatchdogStaleTimeoutSeconds] = useState(
    String(settings.watchdogStaleTimeoutSeconds),
  );
  const [watchdogHeartbeatIntervalSeconds, setWatchdogHeartbeatIntervalSeconds] = useState(
    String(settings.watchdogHeartbeatIntervalSeconds),
  );
  const [modalTokenId, setModalTokenId] = useState("");
  const [modalTokenSecret, setModalTokenSecret] = useState("");

  const { data: llmModels, isLoading: isLoadingLlmModels } = useLlmModels();
  const modelsByProvider = useMemo<
    Readonly<Record<LlmCatalogProvider, ReadonlyArray<LlmModelOption>>>
  >(() => {
    const empty: Record<LlmCatalogProvider, LlmModelOption[]> = { openai: [], anthropic: [] };
    if (llmModels === undefined) {
      return empty;
    }
    for (const option of llmModels) {
      empty[option.provider].push(option);
    }
    return empty;
  }, [llmModels]);

  useEffect(() => {
    if (apiKeySaveResult?.success) {
      setAiApiKey("");
    }
  }, [apiKeySaveResult]);

  useEffect(() => {
    if (modalTokenSaveResult?.success) {
      setModalTokenId("");
      setModalTokenSecret("");
    }
  }, [modalTokenSaveResult]);

  const handleProviderChange = (val: string): void => {
    const provider = val as AIProvider;
    setAiProvider(provider);
    if (provider !== "openai_compatible") {
      setAiBaseUrl("");
    }
    if (provider === "openai" || provider === "anthropic") {
      const options = modelsByProvider[provider];
      const hasCurrent = options.some((option) => option.modelId === aiModelId);
      if (!hasCurrent) {
        setAiModelId(PROVIDER_DEFAULT_MODEL_ID[provider]);
      }
    }
  };

  const handleSubmit = (e: React.FormEvent): void => {
    e.preventDefault();
    onSave({
      aiProvider,
      aiModelId: aiModelId || undefined,
      aiBaseUrl: aiProvider === "openai_compatible" ? aiBaseUrl || undefined : undefined,
      defaultProjectsDir: defaultProjectsDir || undefined,
      storageWarningThresholdGb: storageWarningThresholdGb
        ? Number(storageWarningThresholdGb)
        : undefined,
      watchdogStaleTimeoutSeconds: watchdogStaleTimeoutSeconds
        ? Number(watchdogStaleTimeoutSeconds)
        : undefined,
      watchdogHeartbeatIntervalSeconds: watchdogHeartbeatIntervalSeconds
        ? Number(watchdogHeartbeatIntervalSeconds)
        : undefined,
    });
  };

  const handleSetApiKey = (): void => {
    if (aiApiKey) {
      onSetApiKey(aiApiKey);
    }
  };

  const handleSetModalToken = (): void => {
    if (modalTokenId && modalTokenSecret) {
      onSetModalToken({ tokenId: modalTokenId, tokenSecret: modalTokenSecret });
    }
  };

  return (
    <form id="settings-form" onSubmit={handleSubmit} className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">AI Provider</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="ai-provider">Provider</Label>
            <Select value={aiProvider} onValueChange={handleProviderChange}>
              <SelectTrigger id="ai-provider">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="anthropic">Anthropic</SelectItem>
                <SelectItem value="openai">OpenAI</SelectItem>
                <SelectItem value="openai_compatible">OpenAI-Compatible</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Label htmlFor="ai-api-key">API Key</Label>
              {settings.isAiApiKeySet && (
                <Badge variant="secondary" className="text-xs">
                  Set
                </Badge>
              )}
            </div>
            <div className="flex items-center gap-2">
              <Input
                id="ai-api-key"
                type="password"
                placeholder={settings.isAiApiKeySet ? "••••••••••••••••" : "Enter API key"}
                value={aiApiKey}
                onChange={(e) => setAiApiKey(e.target.value)}
                autoComplete="off"
                className="flex-1"
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleSetApiKey}
                disabled={!aiApiKey || isSavingApiKey}
                className="shrink-0"
              >
                {isSavingApiKey ? (
                  "Saving..."
                ) : apiKeySaveResult?.success ? (
                  <span className="flex items-center gap-1">
                    <Check className="h-3.5 w-3.5" />
                    Saved
                  </span>
                ) : (
                  "Set Key"
                )}
              </Button>
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="ai-model-id">Model</Label>
            {aiProvider === "openai" || aiProvider === "anthropic" ? (
              isLoadingLlmModels ? (
                <span className="font-mono text-[11px] text-ink-3">Loading models…</span>
              ) : (
                <Select value={aiModelId} onValueChange={setAiModelId}>
                  <SelectTrigger id="ai-model-id">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {modelsByProvider[aiProvider].map(({ modelId, label }) => (
                      <SelectItem key={modelId} value={modelId}>
                        {label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )
            ) : (
              <Input
                id="ai-model-id"
                placeholder="model-id"
                value={aiModelId}
                onChange={(e) => setAiModelId(e.target.value)}
              />
            )}
          </div>

          {aiProvider === "openai_compatible" && (
            <div className="space-y-2">
              <Label htmlFor="ai-base-url">Base URL</Label>
              <Input
                id="ai-base-url"
                placeholder="https://api.example.com/v1"
                value={aiBaseUrl}
                onChange={(e) => setAiBaseUrl(e.target.value)}
              />
            </div>
          )}

          <div className="flex items-center gap-3">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onTestConnection}
              disabled={isTestingConnection}
            >
              {isTestingConnection ? "Testing..." : "Test Connection"}
            </Button>
            {testConnectionResult && (
              <Badge variant={testConnectionResult.success ? "secondary" : "destructive"}>
                {testConnectionResult.message}
              </Badge>
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Cloud Training</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-3">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              Modal
            </p>

            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Label>API Token</Label>
                {settings.isModalTokenSet && (
                  <Badge variant="secondary" className="text-xs">
                    Set
                  </Badge>
                )}
              </div>
              <div className="space-y-2">
                <Input
                  id="modal-token-id"
                  type="password"
                  placeholder={settings.isModalTokenSet ? "••••••••••••••••" : "Token ID (ak-...)"}
                  value={modalTokenId}
                  onChange={(e) => setModalTokenId(e.target.value)}
                  autoComplete="off"
                />
                <Input
                  id="modal-token-secret"
                  type="password"
                  placeholder={
                    settings.isModalTokenSet ? "••••••••••••••••" : "Token Secret (as-...)"
                  }
                  value={modalTokenSecret}
                  onChange={(e) => setModalTokenSecret(e.target.value)}
                  autoComplete="off"
                />
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleSetModalToken}
                disabled={!modalTokenId || !modalTokenSecret || isSavingModalToken}
                className="shrink-0"
              >
                {isSavingModalToken ? (
                  "Saving..."
                ) : modalTokenSaveResult?.success ? (
                  <span className="flex items-center gap-1">
                    <Check className="h-3.5 w-3.5" />
                    Saved
                  </span>
                ) : (
                  "Set Token"
                )}
              </Button>
            </div>

            <div className="flex items-center gap-3">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={onTestModalConnection}
                disabled={isTestingModalConnection || !settings.isModalTokenSet}
              >
                {isTestingModalConnection ? "Testing..." : "Test Connection"}
              </Button>
              {modalTestResult && (
                <Badge variant={modalTestResult.success ? "secondary" : "destructive"}>
                  {modalTestResult.message}
                </Badge>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Storage</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="default-projects-dir">Default Projects Directory</Label>
            <Input
              id="default-projects-dir"
              placeholder="/app/projects"
              value={defaultProjectsDir}
              onChange={(e) => setDefaultProjectsDir(e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="storage-warning-threshold">Storage Warning Threshold (GB)</Label>
            <Input
              id="storage-warning-threshold"
              type="number"
              min="1"
              step="1"
              value={storageWarningThresholdGb}
              onChange={(e) => setStorageWarningThresholdGb(e.target.value)}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Watchdog</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="stale-timeout">Stale Timeout (seconds)</Label>
            <Input
              id="stale-timeout"
              type="number"
              min="10"
              step="10"
              value={watchdogStaleTimeoutSeconds}
              onChange={(e) => setWatchdogStaleTimeoutSeconds(e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="heartbeat-interval">Heartbeat Interval (seconds)</Label>
            <Input
              id="heartbeat-interval"
              type="number"
              min="1"
              step="1"
              value={watchdogHeartbeatIntervalSeconds}
              onChange={(e) => setWatchdogHeartbeatIntervalSeconds(e.target.value)}
            />
          </div>
        </CardContent>
      </Card>
    </form>
  );
}
