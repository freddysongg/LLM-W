import * as React from "react";
import { useState } from "react";
import { useSettings, useUpdateSettings, useTestAiConnection } from "@/hooks/useSettings";
import { SettingsForm } from "@/components/settings/settings-form";
import { DefaultRetentionPolicy } from "@/components/settings/default-retention-policy";
import { ExperimentRetentionDays } from "@/components/settings/experiment-retention-days";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import type { UpdateSettingsRequest, ApiKeySaveResult } from "@/types/settings";

interface TestResult {
  readonly success: boolean;
  readonly message: string;
}

export default function SettingsPage(): React.JSX.Element {
  const { data: settings, isLoading, error } = useSettings();
  const updateSettings = useUpdateSettings();
  const saveApiKey = useUpdateSettings();
  const testConnection = useTestAiConnection();
  const { toast } = useToast();
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [apiKeySaveResult, setApiKeySaveResult] = useState<ApiKeySaveResult | null>(null);

  const handleSave = (updates: UpdateSettingsRequest): void => {
    updateSettings.mutate(
      { request: updates },
      {
        onSuccess: () => {
          toast({
            title: "Settings saved",
            description: "Settings saved successfully.",
          });
        },
        onError: () => {
          toast({
            title: "Save failed",
            description: "Failed to save settings.",
            variant: "destructive",
          });
        },
      },
    );
  };

  const handleSetApiKey = (apiKey: string): void => {
    setApiKeySaveResult(null);
    saveApiKey.mutate(
      { request: { aiApiKey: apiKey } },
      {
        onSuccess: () => {
          setApiKeySaveResult({ success: true });
          toast({ title: "API key saved", description: "API key updated successfully." });
        },
        onError: () => {
          setApiKeySaveResult({ success: false });
          toast({
            title: "Failed to save API key",
            description: "Could not update the API key.",
            variant: "destructive",
          });
        },
      },
    );
  };

  const handleTestConnection = (): void => {
    setTestResult(null);
    testConnection.mutate(undefined, {
      onSuccess: (result) => setTestResult(result),
      onError: () => setTestResult({ success: false, message: "Connection failed" }),
    });
  };

  return (
    <div className="p-6 max-w-2xl pb-20">
      <h1 className="text-xl font-semibold mb-6">Settings</h1>

      {isLoading && <div className="text-sm text-muted-foreground">Loading settings...</div>}

      {error && <div className="text-sm text-destructive">Failed to load settings.</div>}

      <div className="space-y-6">
        {settings && (
          <SettingsForm
            settings={settings}
            onSave={handleSave}
            onSetApiKey={handleSetApiKey}
            isSavingApiKey={saveApiKey.isPending}
            apiKeySaveResult={apiKeySaveResult}
            onTestConnection={handleTestConnection}
            isTestingConnection={testConnection.isPending}
            testConnectionResult={testResult}
          />
        )}

        <DefaultRetentionPolicy onChange={() => undefined} />
        <ExperimentRetentionDays onChange={() => undefined} />
      </div>

      <div className="fixed bottom-0 right-0 z-10 flex justify-end border-t border-border bg-background px-6 py-4 shadow-md w-full">
        <Button type="submit" form="settings-form" disabled={updateSettings.isPending}>
          {updateSettings.isPending ? "Saving..." : "Save Settings"}
        </Button>
      </div>
    </div>
  );
}
