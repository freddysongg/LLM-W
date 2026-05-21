import * as React from "react";
import { useState } from "react";
import {
  useSettings,
  useUpdateSettings,
  useTestAiConnection,
  useTestModalConnection,
} from "@/hooks/useSettings";
import { useLockEntered } from "@/hooks/use-lock-entered";
import { useToast } from "@/hooks/use-toast";
import { SettingsForm } from "@/components/settings/settings-form";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { UpdateSettingsRequest, ApiKeySaveResult } from "@/types/settings";

interface TestResult {
  readonly success: boolean;
  readonly message: string;
}

interface ModalTokenCredentials {
  readonly tokenId: string;
  readonly tokenSecret: string;
}

export default function SettingsPage(): React.JSX.Element {
  const { data: settings, isLoading, error } = useSettings();
  const updateSettings = useUpdateSettings();
  const saveApiKey = useUpdateSettings();
  const saveModalToken = useUpdateSettings();
  const testConnection = useTestAiConnection();
  const testModalConn = useTestModalConnection();
  const { toast } = useToast();
  const isAnimationLocked = useLockEntered();

  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [apiKeySaveResult, setApiKeySaveResult] = useState<ApiKeySaveResult | null>(null);
  const [modalTokenSaveResult, setModalTokenSaveResult] = useState<ApiKeySaveResult | null>(null);
  const [modalTestResult, setModalTestResult] = useState<TestResult | null>(null);

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

  const handleSetModalToken = ({ tokenId, tokenSecret }: ModalTokenCredentials): void => {
    setModalTokenSaveResult(null);
    saveModalToken.mutate(
      { request: { modalTokenId: tokenId, modalTokenSecret: tokenSecret } },
      {
        onSuccess: () => {
          setModalTokenSaveResult({ success: true });
          toast({
            title: "Modal token saved",
            description: "Modal API token updated successfully.",
          });
        },
        onError: () => {
          setModalTokenSaveResult({ success: false });
          toast({
            title: "Failed to save Modal token",
            description: "Could not update the Modal API token.",
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

  const handleTestModalConnection = (): void => {
    setModalTestResult(null);
    testModalConn.mutate(undefined, {
      onSuccess: (result) => setModalTestResult(result),
      onError: () => setModalTestResult({ success: false, message: "Connection failed" }),
    });
  };

  const enteredClass = isAnimationLocked ? "entered" : "";

  return (
    <div className="flex flex-col gap-4 p-6">
      <header className={cn("flex items-start justify-between gap-4 enter enter-1", enteredClass)}>
        <div>
          <h1 className="font-mono text-[22px] font-semibold tracking-[-0.01em] text-ink-1">
            Settings
          </h1>
          <p className="mt-1 font-mono text-[11px] text-ink-3">
            ai provider · cloud training · storage · watchdog
          </p>
        </div>
      </header>

      {isLoading && <div className="font-mono text-[11px] text-ink-3">Loading settings…</div>}
      {error && (
        <div className="font-mono text-[11px] text-[color:var(--danger)]">
          Failed to load settings.
        </div>
      )}

      <div className={cn("flex flex-col gap-4 enter enter-2", enteredClass)}>
        {settings ? (
          <SettingsForm
            settings={settings}
            onSave={handleSave}
            onSetApiKey={handleSetApiKey}
            isSavingApiKey={saveApiKey.isPending}
            apiKeySaveResult={apiKeySaveResult}
            onTestConnection={handleTestConnection}
            isTestingConnection={testConnection.isPending}
            testConnectionResult={testResult}
            onSetModalToken={handleSetModalToken}
            isSavingModalToken={saveModalToken.isPending}
            modalTokenSaveResult={modalTokenSaveResult}
            onTestModalConnection={handleTestModalConnection}
            isTestingModalConnection={testModalConn.isPending}
            modalTestResult={modalTestResult}
          />
        ) : null}
        <div className="sticky bottom-0 mt-4 flex justify-end border-t border-hairline bg-surface px-0 py-4">
          <Button
            type="submit"
            form="settings-form"
            variant="primary"
            size="sm"
            disabled={updateSettings.isPending}
          >
            {updateSettings.isPending ? "Saving…" : "Save settings"}
          </Button>
        </div>
      </div>
    </div>
  );
}
