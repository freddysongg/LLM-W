import * as React from "react";
import { useNavigate } from "react-router-dom";
import { Brain, Download, ExternalLink, Layers, Plus, Star, Trash2 } from "lucide-react";
import { useAppStore } from "@/stores/app-store";
import { useModelProfile, useModelArchitecture, useResolveModel } from "@/hooks/useModelProfile";
import { useModelRegistry, useRegisterModelEntry } from "@/hooks/useCatalog";
import {
  useCreateMergedModel,
  useDeleteMergedModel,
  useMergedModels,
} from "@/hooks/useMergedModels";
import { useRuns } from "@/hooks/useRuns";
import type { ModelArchitectureResponse, ModelProfile } from "@/types/model";
import type { ModelRegistryEntry, RegisterModelEntryRequest } from "@/types/model-registry";
import type { MergedModel } from "@/types/merged-model";
import type { Run } from "@/types/run";
import { ModelSourceSelector } from "@/components/model/model-source-selector";
import { ModelIdInput } from "@/components/model/model-id-input";
import { ModelResolveButton } from "@/components/model/model-resolve-button";
import { ArchitectureDiagram } from "@/components/model/architecture-diagram";
import { RegisterModelModal } from "@/components/model/register-model-modal";
import { ServingActions, ServingStatusRow } from "@/components/model/serving-panel";
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { KVList } from "@/components/shared/kv-list";
import { StatusDot } from "@/components/shared/status-dot";
import { RunRow, RunRowCell } from "@/components/shared/run-row";
import { CopyForAI } from "@/components/shared/copy-for-ai";
import { buildModelPrompt } from "@/lib/ai-copy-prompts";
import { useToast } from "@/hooks/use-toast";
import { describeApiError } from "@/lib/api-error";
import { deriveMergedName } from "@/lib/merged-models";
import { cn } from "@/lib/utils";

type ModelsTab = "active" | "registry" | "merged";

function formatParamCount(count: number): string {
  if (count >= 1_000_000_000) return `${(count / 1_000_000_000).toFixed(2)}B`;
  if (count >= 1_000_000) return `${(count / 1_000_000).toFixed(2)}M`;
  if (count >= 1_000) return `${(count / 1_000).toFixed(1)}K`;
  return String(count);
}

function formatDiskEstimate(vramGb: number): string {
  return vramGb >= 1 ? `${vramGb.toFixed(2)} GB` : `${(vramGb * 1024).toFixed(0)} MB`;
}

function formatBytes(bytes: number): string {
  if (bytes <= 0) return "—";
  if (bytes >= 1_000_000_000) return `${(bytes / 1_000_000_000).toFixed(2)} GB`;
  if (bytes >= 1_000_000) return `${(bytes / 1_000_000).toFixed(1)} MB`;
  if (bytes >= 1_000) return `${(bytes / 1_000).toFixed(0)} KB`;
  return `${bytes} B`;
}

function formatRelativeTime(iso: string): string {
  const created = new Date(iso).getTime();
  if (Number.isNaN(created)) return iso;
  const deltaMs = Date.now() - created;
  if (deltaMs < 60_000) return "just now";
  if (deltaMs < 3_600_000) return `${Math.round(deltaMs / 60_000)}m ago`;
  if (deltaMs < 86_400_000) return `${Math.round(deltaMs / 3_600_000)}h ago`;
  return `${Math.round(deltaMs / 86_400_000)}d ago`;
}

function describeAdapter({
  sourceRunId,
  adapterStep,
}: {
  readonly sourceRunId: string | null;
  readonly adapterStep: number | null;
}): string {
  if (sourceRunId === null) return "external adapter";
  const runShort = sourceRunId.slice(0, 8);
  return adapterStep !== null ? `run ${runShort} @ step ${adapterStep}` : `run ${runShort} @ final`;
}

function isMergeableRun(run: Run): boolean {
  return run.status === "completed" && run.lastCheckpointPath !== null;
}

function buildActiveKvRows({
  profile,
  architecture,
  projectId,
}: {
  readonly profile: ModelProfile;
  readonly architecture: ModelArchitectureResponse | undefined;
  readonly projectId: string;
}): ReadonlyArray<{ readonly key: string; readonly value: React.ReactNode }> {
  const layersLabel = architecture
    ? `${(architecture.tree.children ?? []).length || "—"} · params ${formatParamCount(architecture.total_parameters)}`
    : "—";

  return [
    { key: "Architecture", value: profile.architecture_name },
    { key: "Params", value: formatParamCount(profile.total_parameters) },
    { key: "Layers", value: layersLabel },
    {
      key: "Context",
      value: profile.context_length ? `${profile.context_length.toLocaleString()} tokens` : "—",
    },
    { key: "Dtype", value: profile.torch_dtype },
    { key: "Disk", value: formatDiskEstimate(profile.resource_estimate.disk_gb) },
    { key: "License", value: "—" },
    { key: "Serving", value: <ServingStatusRow projectId={projectId} /> },
  ];
}

const REGISTRY_ROW_COLUMNS = "24px minmax(0,1.2fr) 90px 80px 1fr 60px 110px";
const MERGED_ROW_COLUMNS = "20px minmax(0,1.4fr) minmax(0,1fr) 80px 80px 120px";

const REGISTRY_HEADER_STYLE: React.CSSProperties = {
  gridTemplateColumns: REGISTRY_ROW_COLUMNS,
};
const MERGED_ROW_STYLE: React.CSSProperties = {
  gridTemplateColumns: MERGED_ROW_COLUMNS,
};

export default function ModelsPage(): React.JSX.Element {
  const { activeProjectId, modelForm, setModelForm } = useAppStore();
  const { toast } = useToast();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = React.useState<ModelsTab>("active");
  const [isRegisterOpen, setIsRegisterOpen] = React.useState(false);

  const projectId = activeProjectId ?? "";
  const { data: profile, isLoading: isLoadingProfile } = useModelProfile({ projectId });
  const { data: architecture } = useModelArchitecture({ projectId });
  const { data: registryEntries, isLoading: isLoadingRegistry } = useModelRegistry();
  const registry: ReadonlyArray<ModelRegistryEntry> = registryEntries ?? [];
  const registerModelEntry = useRegisterModelEntry();
  const resolveModel = useResolveModel();
  const { data: mergedModels, isLoading: isLoadingMergedModels } = useMergedModels({
    projectId,
  });
  const mergedItems: ReadonlyArray<MergedModel> = mergedModels?.items ?? [];
  const { data: runsForProject } = useRuns({ projectId });
  const mergeableRuns = React.useMemo(
    () => (runsForProject ?? []).filter(isMergeableRun),
    [runsForProject],
  );
  const createMergedModel = useCreateMergedModel({ projectId });
  const deleteMergedModel = useDeleteMergedModel({ projectId });
  const [isMergeDialogOpen, setIsMergeDialogOpen] = React.useState(false);
  const [mergeRunId, setMergeRunId] = React.useState<string>("");

  React.useEffect(() => {
    if (profile && !modelForm.modelId) {
      setModelForm({ source: profile.source, modelId: profile.model_id });
    }
  }, [profile, modelForm.modelId, setModelForm]);

  const handleResolve = (): void => {
    if (!projectId || !modelForm.modelId.trim()) return;
    resolveModel.mutate({
      projectId,
      request: { source: modelForm.source, model_id: modelForm.modelId.trim() },
    });
  };

  const handleRegister = (draft: RegisterModelEntryRequest): void => {
    registerModelEntry.mutate(draft, {
      onSuccess: (entry) => {
        setIsRegisterOpen(false);
        toast({
          title: "Model registered",
          description: `${entry.name} · ${entry.source} · ${entry.path ?? ""}`.trim(),
        });
      },
      onError: (cause) => {
        toast({
          title: "Register failed",
          description: describeApiError({
            cause,
            fallback: "Could not persist the registry entry.",
          }),
          variant: "destructive",
        });
      },
    });
  };

  const handleOpenMergeDialog = (): void => {
    setMergeRunId(mergeableRuns[0]?.id ?? "");
    setIsMergeDialogOpen(true);
  };

  const handleConfirmMerge = (): void => {
    if (!mergeRunId) return;
    createMergedModel.mutate(
      { sourceRunId: mergeRunId },
      {
        onSuccess: (merged) => {
          setIsMergeDialogOpen(false);
          toast({
            title: "Merged model created",
            description: `${deriveMergedName({
              baseModelId: merged.baseModelId,
              adapterStep: merged.adapterStep,
            })} · ${formatBytes(merged.fileSizeBytes)}`,
          });
        },
        onError: (cause) => {
          toast({
            title: "Merge failed",
            description: describeApiError({
              cause,
              fallback: "Merging the adapter into the base model failed.",
            }),
            variant: "destructive",
          });
        },
      },
    );
  };

  const handleCopyMergedPath = async (filePath: string): Promise<void> => {
    try {
      await navigator.clipboard.writeText(filePath);
      toast({
        title: "Path copied",
        description: filePath,
      });
    } catch {
      toast({
        title: "Could not copy path",
        description: filePath,
        variant: "destructive",
      });
    }
  };

  const handleDeleteMerged = (mergedId: string): void => {
    deleteMergedModel.mutate(mergedId, {
      onSuccess: () => toast({ title: "Merged model deleted" }),
      onError: (cause) =>
        toast({
          title: "Delete failed",
          description: describeApiError({
            cause,
            fallback: "Could not delete merged model.",
          }),
          variant: "destructive",
        }),
    });
  };

  const canResolve = Boolean(projectId) && modelForm.modelId.trim().length > 0;
  const activeKvRows = React.useMemo(
    () => (profile ? buildActiveKvRows({ profile, architecture, projectId }) : []),
    [profile, architecture, projectId],
  );

  return (
    <div className="flex h-full flex-col">
      <div className="flex h-14 items-center justify-between border-b border-hairline px-6">
        <div>
          <h1 className="font-mono text-[16px] font-semibold tracking-tight text-ink-1">Models</h1>
          <p className="font-mono text-[11px] text-ink-3">
            base checkpoints · adapters · merged weights
          </p>
        </div>
        <div className="flex items-center gap-2">
          {profile && architecture && (
            <CopyForAI buildPrompt={() => buildModelPrompt({ profile, architecture })} />
          )}
          <Button variant="primary" size="sm" onClick={() => setIsRegisterOpen(true)}>
            <Plus className="size-3" aria-hidden="true" />
            Register
          </Button>
        </div>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto p-6">
        {!activeProjectId && (
          <p className="font-mono text-[12px] text-ink-3">Select a project to resolve a model.</p>
        )}

        {activeProjectId && (
          <>
            <Card>
              <CardHeader>
                <CardTitle>Resolve model</CardTitle>
                <Badge variant="iris" dot={false}>
                  {modelForm.source}
                </Badge>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-1.5">
                  <p className="font-mono text-[10px] uppercase tracking-[0.08em] text-ink-3">
                    Source
                  </p>
                  <ModelSourceSelector
                    source={modelForm.source}
                    onChange={(source) => setModelForm({ source })}
                  />
                </div>
                <div className="space-y-1.5">
                  <p className="font-mono text-[10px] uppercase tracking-[0.08em] text-ink-3">
                    Model ID
                  </p>
                  <ModelIdInput
                    source={modelForm.source}
                    value={modelForm.modelId}
                    onChange={(modelId) => setModelForm({ modelId })}
                    isDisabled={resolveModel.isPending}
                  />
                </div>
                <div className="flex items-center gap-3">
                  <ModelResolveButton
                    onResolve={handleResolve}
                    isResolving={resolveModel.isPending}
                    isDisabled={!canResolve}
                  />
                  {resolveModel.isError && (
                    <span className="font-mono text-[11px] text-[color:var(--danger)]">
                      {resolveModel.error instanceof Error
                        ? resolveModel.error.message
                        : "Resolution failed"}
                    </span>
                  )}
                </div>
              </CardContent>
            </Card>

            <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as ModelsTab)}>
              <TabsList>
                <TabsTrigger value="active">Active model</TabsTrigger>
                <TabsTrigger value="registry">
                  Registry
                  <span className="ml-1 rounded-full bg-surface-2 px-1.5 font-mono text-[9px] text-ink-3">
                    {registry.length}
                  </span>
                </TabsTrigger>
                <TabsTrigger value="merged">
                  Merged
                  <span className="ml-1 rounded-full bg-surface-2 px-1.5 font-mono text-[9px] text-ink-3">
                    {mergedItems.length}
                  </span>
                </TabsTrigger>
              </TabsList>

              <TabsContent value="active">
                {isLoadingProfile && (
                  <p className="font-mono text-[11px] text-ink-3">Loading model profile…</p>
                )}
                {!isLoadingProfile && !profile && (
                  <p className="font-mono text-[11px] text-ink-3">
                    No model resolved for this project yet. Enter a model ID above and resolve it.
                  </p>
                )}
                {profile && (
                  <div className="grid gap-4 lg:grid-cols-2">
                    <Card>
                      <CardHeader>
                        <div className="space-y-0.5">
                          <CardTitle>{profile.model_id}</CardTitle>
                          <p className="font-mono text-[11px] text-ink-3">
                            base · {profile.torch_dtype} ·{" "}
                            {profile.context_length
                              ? `${(profile.context_length / 1024).toFixed(0)}k ctx`
                              : "ctx —"}
                          </p>
                        </div>
                        <Badge variant="iris" dot={false}>
                          ACTIVE
                        </Badge>
                      </CardHeader>
                      <CardContent>
                        <KVList rows={activeKvRows} />
                      </CardContent>
                      <CardFooter>
                        <div className="flex items-center gap-2">
                          <Button variant="outline" size="sm" onClick={() => navigate("/weights")}>
                            <Layers className="size-3" aria-hidden="true" />
                            Inspect weights
                          </Button>
                          <ServingActions projectId={projectId} />
                        </div>
                        <div className="flex items-center gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() =>
                              toast({
                                title: "Opened HF page",
                                description: profile.model_id,
                              })
                            }
                          >
                            <ExternalLink className="size-3" aria-hidden="true" />
                            HF page
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() =>
                              toast({ title: "Export queued", description: "Exporting model." })
                            }
                          >
                            <Download className="size-3" aria-hidden="true" />
                            Export
                          </Button>
                        </div>
                      </CardFooter>
                    </Card>

                    <Card>
                      <CardHeader>
                        <CardTitle>Architecture diagram</CardTitle>
                      </CardHeader>
                      <CardContent>
                        {architecture ? (
                          <ArchitectureDiagram architecture={architecture} />
                        ) : (
                          <p className="font-mono text-[11px] text-ink-3">
                            Architecture metadata unavailable for this model.
                          </p>
                        )}
                      </CardContent>
                    </Card>
                  </div>
                )}
              </TabsContent>

              <TabsContent value="registry">
                <Card>
                  <RunRow isHeader style={REGISTRY_HEADER_STYLE}>
                    <span />
                    <span>Model</span>
                    <span>Params</span>
                    <span>Ctx</span>
                    <span>License</span>
                    <span>Src</span>
                    <span className="text-right">Actions</span>
                  </RunRow>
                  {isLoadingRegistry ? (
                    <div className="p-3 font-mono text-[11px] text-ink-3">Loading registry…</div>
                  ) : registry.length === 0 ? (
                    <div className="p-3 font-mono text-[11px] text-ink-3">
                      No models registered.
                    </div>
                  ) : (
                    registry.map((model) => (
                      <RunRow
                        key={model.name}
                        style={REGISTRY_HEADER_STYLE}
                        onClick={() => toast({ title: `Activated ${model.name}` })}
                      >
                        <span
                          aria-hidden="true"
                          className={cn(
                            "inline-grid place-items-center",
                            model.isPinned ? "text-[color:var(--warn)]" : "text-ink-4",
                          )}
                        >
                          {model.isPinned ? (
                            <Star className="size-3.5" />
                          ) : (
                            <Brain className="size-3.5" />
                          )}
                        </span>
                        <div className="truncate font-mono text-[12px] text-ink-1">
                          {model.name}
                        </div>
                        <RunRowCell>{model.params ?? "—"}</RunRowCell>
                        <RunRowCell>{model.context ?? "—"}</RunRowCell>
                        <RunRowCell>{model.license ?? "—"}</RunRowCell>
                        <RunRowCell>{model.source}</RunRowCell>
                        <div className="flex items-center justify-end gap-1">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={(event) => {
                              event.stopPropagation();
                              toast({ title: `Activated ${model.name}` });
                            }}
                          >
                            Use
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="size-7"
                            onClick={(event) => {
                              event.stopPropagation();
                              toast({ title: "Opened HF page" });
                            }}
                            aria-label="Open HF page"
                          >
                            <ExternalLink className="size-3" aria-hidden="true" />
                          </Button>
                        </div>
                      </RunRow>
                    ))
                  )}
                </Card>
              </TabsContent>

              <TabsContent value="merged">
                <Card>
                  <div className="flex items-center justify-between border-b border-hairline px-3 py-2">
                    <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-ink-3">
                      {mergedItems.length} merged model
                      {mergedItems.length === 1 ? "" : "s"}
                    </span>
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={handleOpenMergeDialog}
                      disabled={mergeableRuns.length === 0}
                    >
                      <Plus className="size-3" aria-hidden="true" />
                      Merge from run
                    </Button>
                  </div>
                  {isLoadingMergedModels ? (
                    <div className="p-3 font-mono text-[11px] text-ink-3">
                      Loading merged models…
                    </div>
                  ) : mergedItems.length === 0 ? (
                    <div className="p-3 font-mono text-[11px] text-ink-3">
                      No merged models yet. Use "Merge from run" to fuse a completed run's adapter
                      into its base.
                    </div>
                  ) : (
                    mergedItems.map((entry) => (
                      <RunRow
                        key={entry.id}
                        style={MERGED_ROW_STYLE}
                        onClick={() =>
                          toast({
                            title: deriveMergedName({
                              baseModelId: entry.baseModelId,
                              adapterStep: entry.adapterStep,
                            }),
                            description: entry.filePath,
                          })
                        }
                      >
                        <StatusDot status="success" />
                        <div className="min-w-0">
                          <div className="truncate font-mono text-[12px] text-ink-1">
                            {deriveMergedName({
                              baseModelId: entry.baseModelId,
                              adapterStep: entry.adapterStep,
                            })}
                          </div>
                          <div className="truncate font-mono text-[10px] text-ink-3">
                            {describeAdapter({
                              sourceRunId: entry.sourceRunId,
                              adapterStep: entry.adapterStep,
                            })}
                          </div>
                        </div>
                        <RunRowCell>base: {entry.baseModelId}</RunRowCell>
                        <RunRowCell>{formatBytes(entry.fileSizeBytes)}</RunRowCell>
                        <RunRowCell align="end">{formatRelativeTime(entry.createdAt)}</RunRowCell>
                        <div className="flex items-center justify-end gap-1">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={(event) => {
                              event.stopPropagation();
                              void handleCopyMergedPath(entry.filePath);
                            }}
                            aria-label="Copy disk path"
                          >
                            <Download className="size-3" aria-hidden="true" />
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={(event) => {
                              event.stopPropagation();
                              toast({
                                title: "Push to HuggingFace (not yet wired)",
                                description:
                                  "Direct push to HF is a planned follow-up; copy the disk path to upload via the HF CLI for now.",
                              });
                            }}
                            aria-label="Push to HuggingFace"
                          >
                            <ExternalLink className="size-3" aria-hidden="true" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="size-7"
                            onClick={(event) => {
                              event.stopPropagation();
                              handleDeleteMerged(entry.id);
                            }}
                            disabled={deleteMergedModel.isPending}
                            aria-label="Delete merged model"
                          >
                            <Trash2 className="size-3" aria-hidden="true" />
                          </Button>
                        </div>
                      </RunRow>
                    ))
                  )}
                </Card>
              </TabsContent>
            </Tabs>
          </>
        )}
      </div>

      <RegisterModelModal
        isOpen={isRegisterOpen}
        isPending={registerModelEntry.isPending}
        onOpenChange={setIsRegisterOpen}
        onRegister={handleRegister}
      />

      <Dialog open={isMergeDialogOpen} onOpenChange={(next) => setIsMergeDialogOpen(next)}>
        <DialogContent className="max-w-[520px]">
          <DialogHeader>
            <DialogTitle>Merge run into base model</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-4 px-6 py-5">
            <p className="font-mono text-[11px] text-ink-3">
              Fuses the run's saved peft adapter into a copy of the project's base model. Result
              lands under <code className="font-mono text-ink-2">projects/{"<id>"}/merged/</code>.
              Merge is synchronous and can take minutes on large bases.
            </p>
            <div className="space-y-2">
              <Label htmlFor="merge-run-select" className="caps text-ink-3">
                Source run
              </Label>
              <Select value={mergeRunId} onValueChange={(value) => setMergeRunId(value)}>
                <SelectTrigger id="merge-run-select">
                  <SelectValue placeholder="Select a completed run" />
                </SelectTrigger>
                <SelectContent>
                  {mergeableRuns.map((run) => (
                    <SelectItem key={run.id} value={run.id}>
                      {run.id.slice(0, 8)} · step {run.currentStep}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {mergeableRuns.length === 0 && (
                <p className="font-mono text-[11px] text-ink-3">
                  No completed runs with a saved checkpoint to merge from.
                </p>
              )}
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsMergeDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              onClick={handleConfirmMerge}
              disabled={!mergeRunId || createMergedModel.isPending}
            >
              {createMergedModel.isPending ? "Merging…" : "Merge"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
