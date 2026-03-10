import * as React from "react";
import { useState, useEffect } from "react";
import type { AppSettings, UpdateSettingsRequest, ApiKeySaveResult } from "@/types/settings";
import type { AIProvider } from "@/types/config";
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

const OPENAI_MODELS = [
  "gpt-4o",
  "gpt-4o-mini",
  "gpt-4-turbo",
  "gpt-3.5-turbo",
  "o1",
  "o1-mini",
  "o3-mini",
] as const;
const CLAUDE_MODELS = [
  "claude-opus-4-6",
  "claude-sonnet-4-6",
  "claude-sonnet-4-5-20250514",
  "claude-haiku-4-5-20251001",
] as const;

type OpenAIModel = (typeof OPENAI_MODELS)[number];
type ClaudeModel = (typeof CLAUDE_MODELS)[number];

interface SettingsFormProps {
  readonly settings: AppSettings;
  readonly onSave: (updates: UpdateSettingsRequest) => void;
  readonly onSetApiKey: (apiKey: string) => void;
  readonly isSavingApiKey: boolean;
  readonly apiKeySaveResult: ApiKeySaveResult | null;
  readonly onTestConnection: () => void;
  readonly isTestingConnection: boolean;
  readonly testConnectionResult: { readonly success: boolean; readonly message: string } | null;
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

  useEffect(() => {
    if (apiKeySaveResult?.success) {
      setAiApiKey("");
    }
  }, [apiKeySaveResult]);

  const handleProviderChange = (val: string): void => {
    const provider = val as AIProvider;
    setAiProvider(provider);
    if (provider !== "openai_compatible") {
      setAiBaseUrl("");
    }
    if (provider === "openai" && !(OPENAI_MODELS as readonly string[]).includes(aiModelId)) {
      setAiModelId("gpt-4o");
    }
    if (provider === "anthropic" && !(CLAUDE_MODELS as readonly string[]).includes(aiModelId)) {
      setAiModelId("claude-sonnet-4-6");
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
            {aiProvider === "openai" ? (
              <Select value={aiModelId as OpenAIModel} onValueChange={setAiModelId}>
                <SelectTrigger id="ai-model-id">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {OPENAI_MODELS.map((m) => (
                    <SelectItem key={m} value={m}>
                      {m}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : aiProvider === "anthropic" ? (
              <Select value={aiModelId as ClaudeModel} onValueChange={setAiModelId}>
                <SelectTrigger id="ai-model-id">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {CLAUDE_MODELS.map((m) => (
                    <SelectItem key={m} value={m}>
                      {m}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
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
