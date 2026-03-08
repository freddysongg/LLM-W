import * as React from "react";
import { useState } from "react";
import { useSettings, useUpdateSettings, useTestAiConnection } from "@/hooks/useSettings";
import { SettingsForm } from "@/components/settings/settings-form";
import type { UpdateSettingsRequest } from "@/types/settings";

interface TestResult {
  readonly success: boolean;
  readonly message: string;
}

export default function SettingsPage(): React.JSX.Element {
  const { data: settings, isLoading, error } = useSettings();
  const updateSettings = useUpdateSettings();
  const testConnection = useTestAiConnection();
  const [testResult, setTestResult] = useState<TestResult | null>(null);

  const handleSave = (updates: UpdateSettingsRequest): void => {
    updateSettings.mutate({ request: updates });
  };

  const handleTestConnection = (): void => {
    setTestResult(null);
    testConnection.mutate(undefined, {
      onSuccess: (result) => setTestResult(result),
      onError: () => setTestResult({ success: false, message: "Connection failed" }),
    });
  };

  return (
    <div className="p-6 max-w-2xl">
      <h1 className="text-xl font-semibold mb-6">Settings</h1>

      {isLoading && <div className="text-sm text-muted-foreground">Loading settings...</div>}

      {error && <div className="text-sm text-destructive">Failed to load settings.</div>}

      {settings && (
        <SettingsForm
          settings={settings}
          onSave={handleSave}
          isSaving={updateSettings.isPending}
          onTestConnection={handleTestConnection}
          isTestingConnection={testConnection.isPending}
          testConnectionResult={testResult}
        />
      )}
    </div>
  );
}
