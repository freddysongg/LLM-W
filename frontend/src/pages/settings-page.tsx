import * as React from "react";
import { useState } from "react";
import { Copy, Plus, Cpu, Cloud } from "lucide-react";
import {
  useSettings,
  useUpdateSettings,
  useTestAiConnection,
  useTestModalConnection,
} from "@/hooks/useSettings";
import { useLockEntered } from "@/hooks/use-lock-entered";
import { useToast } from "@/hooks/use-toast";
import { SettingsForm } from "@/components/settings/settings-form";
import { DefaultRetentionPolicy } from "@/components/settings/default-retention-policy";
import { ExperimentRetentionDays } from "@/components/settings/experiment-retention-days";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { RunRow, RunRowCell } from "@/components/shared/run-row";
import { CURRENT_USER } from "@/lib/current-user";
import { cn } from "@/lib/utils";
import type { UpdateSettingsRequest, ApiKeySaveResult } from "@/types/settings";

type SettingsTab = "workspace" | "compute" | "keys" | "members";

interface TestResult {
  readonly success: boolean;
  readonly message: string;
}

interface ComputeEntry {
  readonly name: string;
  readonly status: "connected" | "disconnected";
  readonly detail: string;
  readonly icon: "cloud" | "cpu";
}

interface ApiKeyEntry {
  readonly id: string;
  readonly name: string;
  readonly maskedKey: string;
  readonly createdAgo: string;
  readonly lastUsed: string;
}

interface ModalTokenCredentials {
  readonly tokenId: string;
  readonly tokenSecret: string;
}

interface ComputeRowProps {
  readonly entry: ComputeEntry;
  readonly onAction: (label: string) => void;
}

interface WorkspaceTabProps {
  readonly settings: Parameters<typeof SettingsForm>[0]["settings"];
  readonly onSave: (updates: UpdateSettingsRequest) => void;
  readonly onSetApiKey: (apiKey: string) => void;
  readonly isSavingApiKey: boolean;
  readonly apiKeySaveResult: ApiKeySaveResult | null;
  readonly onTestConnection: () => void;
  readonly isTestingConnection: boolean;
  readonly testConnectionResult: TestResult | null;
  readonly onSetModalToken: (credentials: ModalTokenCredentials) => void;
  readonly isSavingModalToken: boolean;
  readonly modalTokenSaveResult: ApiKeySaveResult | null;
  readonly onTestModalConnection: () => void;
  readonly isTestingModalConnection: boolean;
  readonly modalTestResult: TestResult | null;
}

// TODO(P8): compute integrations are stubbed until a compute endpoint is wired -- remove when available
const COMPUTE_STUB: ReadonlyArray<ComputeEntry> = [
  {
    name: "Modal",
    status: "connected",
    detail: "workspace: acme · 2× a100-40gb reserved",
    icon: "cloud",
  },
  {
    name: "Local GPU",
    status: "connected",
    detail: "rtx4090 · 24GB · workstation-01",
    icon: "cpu",
  },
  {
    name: "RunPod",
    status: "disconnected",
    detail: "link account to use on-demand pods",
    icon: "cpu",
  },
  { name: "SageMaker", status: "disconnected", detail: "AWS integration", icon: "cloud" },
];

// TODO(P8): API key list is stubbed until a keys endpoint is wired -- remove when available
const API_KEY_STUB: ReadonlyArray<ApiKeyEntry> = [
  {
    id: "prod-ingest",
    name: "prod-ingest",
    maskedKey: "sk_live_••••••••3d2a",
    createdAgo: "created 3d ago",
    lastUsed: "4h ago",
  },
  {
    id: "local-dev",
    name: "local-dev",
    maskedKey: "sk_test_••••••••f4c1",
    createdAgo: "created 2w ago",
    lastUsed: "2m ago",
  },
  {
    id: "eval-pipeline",
    name: "eval-pipeline",
    maskedKey: "sk_live_••••••••88ab",
    createdAgo: "created 1mo ago",
    lastUsed: "1d ago",
  },
];

function ComputeRow({ entry, onAction }: ComputeRowProps): React.JSX.Element {
  const Icon = entry.icon === "cloud" ? Cloud : Cpu;
  return (
    <RunRow style={{ gridTemplateColumns: "24px 1fr 120px 100px" }}>
      <Icon className="h-3.5 w-3.5 text-ink-3" aria-hidden="true" />
      <div className="min-w-0">
        <div className="truncate text-[13px] font-medium text-ink-1">{entry.name}</div>
        <div className="truncate font-mono text-[10.5px] text-ink-3">{entry.detail}</div>
      </div>
      <div>
        {entry.status === "connected" ? (
          <Badge variant="success" dot={false}>
            connected
          </Badge>
        ) : (
          <Badge dot={false}>off</Badge>
        )}
      </div>
      <Button
        variant="outline"
        size="sm"
        onClick={() => onAction(entry.status === "connected" ? "Configure" : "Connect")}
      >
        {entry.status === "connected" ? "Configure" : "Connect"}
      </Button>
    </RunRow>
  );
}

function WorkspaceTab({
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
}: WorkspaceTabProps): React.JSX.Element {
  return (
    <div className="flex flex-col gap-4">
      <SettingsForm
        settings={settings}
        onSave={onSave}
        onSetApiKey={onSetApiKey}
        isSavingApiKey={isSavingApiKey}
        apiKeySaveResult={apiKeySaveResult}
        onTestConnection={onTestConnection}
        isTestingConnection={isTestingConnection}
        testConnectionResult={testConnectionResult}
        onSetModalToken={onSetModalToken}
        isSavingModalToken={isSavingModalToken}
        modalTokenSaveResult={modalTokenSaveResult}
        onTestModalConnection={onTestModalConnection}
        isTestingModalConnection={isTestingModalConnection}
        modalTestResult={modalTestResult}
      />
      <DefaultRetentionPolicy onChange={() => undefined} />
      <ExperimentRetentionDays onChange={() => undefined} />
    </div>
  );
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
  const [isNewKeyOpen, setIsNewKeyOpen] = useState<boolean>(false);
  const [newKeyName, setNewKeyName] = useState<string>("");

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

  const handleCopyKey = async (maskedKey: string): Promise<void> => {
    try {
      await navigator.clipboard.writeText(maskedKey);
      toast({ title: "Copied", description: "API key copied to clipboard." });
    } catch (copyError) {
      toast({
        title: "Copy failed",
        description: copyError instanceof Error ? copyError.message : "Clipboard access denied.",
        variant: "destructive",
      });
    }
  };

  const handleCreateNewKey = (): void => {
    if (!newKeyName.trim()) return;
    toast({
      title: "Key created",
      description: `Created key "${newKeyName.trim()}" (stub).`,
    });
    setNewKeyName("");
    setIsNewKeyOpen(false);
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
            workspace · compute · keys · members
          </p>
        </div>
      </header>

      {isLoading && <div className="font-mono text-[11px] text-ink-3">Loading settings…</div>}
      {error && (
        <div className="font-mono text-[11px] text-[color:var(--danger)]">
          Failed to load settings.
        </div>
      )}

      <Tabs
        defaultValue={"workspace" satisfies SettingsTab}
        className={cn("flex flex-col gap-4 enter enter-2", enteredClass)}
      >
        <TabsList>
          <TabsTrigger value="workspace">Workspace</TabsTrigger>
          <TabsTrigger value="compute">Compute</TabsTrigger>
          <TabsTrigger value="keys">API keys</TabsTrigger>
          <TabsTrigger value="members">Members</TabsTrigger>
        </TabsList>

        <TabsContent value="workspace" className="mt-0">
          {settings ? (
            <WorkspaceTab
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
        </TabsContent>

        <TabsContent value="compute" className="mt-0">
          <Card className="p-0">
            <CardHeader className="py-3">
              <CardTitle>Connected compute</CardTitle>
            </CardHeader>
            <div>
              {COMPUTE_STUB.map((entry) => (
                <ComputeRow
                  key={entry.name}
                  entry={entry}
                  onAction={(action) =>
                    toast({
                      title: action,
                      description: `${action} ${entry.name} (stub).`,
                    })
                  }
                />
              ))}
            </div>
          </Card>
        </TabsContent>

        <TabsContent value="keys" className="mt-0">
          <Card className="p-0">
            <CardHeader className="py-3">
              <CardTitle>API keys</CardTitle>
              <Button variant="primary" size="sm" onClick={() => setIsNewKeyOpen(true)}>
                <Plus aria-hidden="true" />
                New key
              </Button>
            </CardHeader>
            <div>
              {API_KEY_STUB.map((entry) => (
                <RunRow
                  key={entry.id}
                  style={{ gridTemplateColumns: "20px 1fr 220px 120px 140px" }}
                >
                  <span
                    className="h-2 w-2 rounded-full bg-[color:var(--iris-3)]"
                    aria-hidden="true"
                  />
                  <div className="min-w-0">
                    <div className="truncate text-[13px] font-medium text-ink-1">{entry.name}</div>
                    <div className="truncate font-mono text-[10.5px] text-ink-3">
                      {entry.createdAgo}
                    </div>
                  </div>
                  <RunRowCell>{entry.maskedKey}</RunRowCell>
                  <RunRowCell>used {entry.lastUsed}</RunRowCell>
                  <div className="flex items-center justify-end gap-1.5">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        void handleCopyKey(entry.maskedKey);
                      }}
                      aria-label={`Copy ${entry.name} key`}
                    >
                      <Copy aria-hidden="true" />
                      Copy
                    </Button>
                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <Button variant="outline" size="sm">
                          Revoke
                        </Button>
                      </AlertDialogTrigger>
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>Revoke API key?</AlertDialogTitle>
                          <AlertDialogDescription>
                            Revoking <span className="font-mono">{entry.name}</span> cannot be
                            undone.
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel>Cancel</AlertDialogCancel>
                          <AlertDialogAction
                            onClick={() =>
                              toast({
                                title: "Revoked",
                                description: `Key "${entry.name}" revoked (stub).`,
                                variant: "destructive",
                              })
                            }
                            className="bg-[color:var(--danger)] text-[color:var(--surface)] border-[color:var(--danger)] hover:bg-[color-mix(in_oklch,var(--danger)_88%,black)]"
                          >
                            Revoke
                          </AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  </div>
                </RunRow>
              ))}
            </div>
          </Card>
        </TabsContent>

        <TabsContent value="members" className="mt-0">
          <Card className="p-0">
            <CardHeader className="py-3">
              <CardTitle>Members</CardTitle>
              <Badge dot={false}>you</Badge>
            </CardHeader>
            <div>
              <RunRow style={{ gridTemplateColumns: "32px 1fr 130px" }}>
                <span
                  aria-hidden="true"
                  className="grid h-7 w-7 place-items-center rounded-full font-mono text-[10px] font-semibold"
                  style={{ background: CURRENT_USER.avatarColor, color: "var(--surface)" }}
                >
                  {CURRENT_USER.initials}
                </span>
                <div className="min-w-0">
                  <div className="truncate text-[13px] font-medium text-ink-1">
                    {CURRENT_USER.name}
                  </div>
                  <div className="truncate font-mono text-[10.5px] text-ink-3">
                    {CURRENT_USER.email}
                  </div>
                </div>
                <Badge variant="iris" dot={false}>
                  owner
                </Badge>
              </RunRow>
            </div>
          </Card>
        </TabsContent>
      </Tabs>

      <Dialog open={isNewKeyOpen} onOpenChange={setIsNewKeyOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <div className="flex flex-col gap-1.5">
              <DialogTitle>New API key</DialogTitle>
              <DialogDescription>Create a new key for programmatic access.</DialogDescription>
            </div>
          </DialogHeader>
          <div className="flex flex-col gap-3 px-6 py-4">
            <Label htmlFor="new-key-name" className="text-[11px] text-ink-3">
              Key name
            </Label>
            <Input
              id="new-key-name"
              placeholder="pipeline-prod"
              value={newKeyName}
              onChange={(event) => setNewKeyName(event.target.value)}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsNewKeyOpen(false)}>
              Cancel
            </Button>
            <Button variant="primary" onClick={handleCreateNewKey} disabled={!newKeyName.trim()}>
              Create key
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
