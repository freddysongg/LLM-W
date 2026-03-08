import * as React from "react";
import { useState } from "react";
import type { AppSettings, UpdateSettingsRequest } from "@/types/settings";
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

interface SettingsFormProps {
  readonly settings: AppSettings;
  readonly onSave: (updates: UpdateSettingsRequest) => void;
  readonly onTestConnection: () => void;
  readonly isTestingConnection: boolean;
  readonly testConnectionResult: { readonly success: boolean; readonly message: string } | null;
}

export function SettingsForm({
  settings,
  onSave,
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

  const handleSubmit = (e: React.FormEvent): void => {
    e.preventDefault();
    const updates: UpdateSettingsRequest = {
      aiProvider,
      aiModelId: aiModelId || undefined,
      aiBaseUrl: aiBaseUrl || undefined,
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
    };
    if (aiApiKey) {
      onSave({ ...updates, aiApiKey });
    } else {
      onSave(updates);
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
            <Select value={aiProvider} onValueChange={(val) => setAiProvider(val as AIProvider)}>
              <SelectTrigger id="ai-provider">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="anthropic">Anthropic</SelectItem>
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
            <Input
              id="ai-api-key"
              type="password"
              placeholder={settings.isAiApiKeySet ? "••••••••••••••••" : "Enter API key"}
              value={aiApiKey}
              onChange={(e) => setAiApiKey(e.target.value)}
              autoComplete="off"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="ai-model-id">Model ID</Label>
            <Input
              id="ai-model-id"
              placeholder="claude-sonnet-4-20250514"
              value={aiModelId}
              onChange={(e) => setAiModelId(e.target.value)}
            />
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
