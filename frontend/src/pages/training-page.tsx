import * as React from "react";
import { parse as parseYaml, stringify as stringifyYaml } from "yaml";
import { Download, FileText, Play } from "lucide-react";
import { useAppStore } from "@/stores/app-store";
import { useActiveConfig, useSaveConfig } from "@/hooks/useConfigs";
import { useCreateRun, useRuns } from "@/hooks/useRuns";
import { useRunSummaries } from "@/hooks/useRunSummaries";
import { useModelProfile } from "@/hooks/useModelProfile";
import { useDatasetProfile } from "@/hooks/useDatasetProfile";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { NoProjectSelected } from "@/components/shared/no-project-selected";
import { CopyForAI } from "@/components/shared/copy-for-ai";
import { buildTrainingPrompt } from "@/lib/ai-copy-prompts";
import { denormalizeYamlConfig, normalizeYamlConfig } from "@/lib/yaml-config";
import type { Run } from "@/types/run";
import type { RunSummary } from "@/types/run-summary";
import type { TrainingConfig, WorkbenchConfig } from "@/types/config";
import { useToast } from "@/hooks/use-toast";
import { describeApiError } from "@/lib/api-error";
import {
  TrainingForm,
  type TrainingFormSlice,
  type TrainingFormTab,
  type TrainingFormUpdate,
  type TrainingMethod,
} from "@/components/training/training-form";
import { TrainingHistoryTab } from "@/components/training/training-history-tab";
import { TrainingPresetsPanel } from "@/components/training/training-presets-panel";
import { YamlPreviewDialog } from "@/components/training/yaml-preview-dialog";
import { LaunchRunDialog } from "@/components/training/launch-run-dialog";

type PageTab = TrainingFormTab | "history";

function sliceFromConfig(config: WorkbenchConfig): TrainingFormSlice {
  const { training, optimization, adapters, execution, preprocessing } = config;
  return { training, optimization, adapters, execution, preprocessing };
}

function mergeSlice({
  current,
  update,
}: {
  readonly current: TrainingFormSlice;
  readonly update: TrainingFormUpdate;
}): TrainingFormSlice {
  return {
    training: update.training ? { ...current.training, ...update.training } : current.training,
    optimization: update.optimization
      ? { ...current.optimization, ...update.optimization }
      : current.optimization,
    adapters: update.adapters ? { ...current.adapters, ...update.adapters } : current.adapters,
    execution: update.execution ? { ...current.execution, ...update.execution } : current.execution,
    preprocessing: update.preprocessing
      ? { ...current.preprocessing, ...update.preprocessing }
      : current.preprocessing,
  };
}

function composeFullConfig({
  base,
  slice,
}: {
  readonly base: WorkbenchConfig;
  readonly slice: TrainingFormSlice;
}): WorkbenchConfig {
  return {
    ...base,
    training: slice.training,
    optimization: slice.optimization,
    adapters: slice.adapters,
    execution: slice.execution,
    preprocessing: slice.preprocessing,
  };
}

function resolveMethod(slice: TrainingFormSlice): TrainingMethod {
  const { adapters } = slice;
  if (!adapters.enabled) return "full";
  if (adapters.type === "qlora") return "qlora";
  return "lora";
}

export default function TrainingPage(): React.JSX.Element {
  const { activeProjectId } = useAppStore();
  const projectId = activeProjectId ?? "";
  const { toast } = useToast();

  const { data: configVersion, isLoading, error } = useActiveConfig({ projectId });
  const saveConfig = useSaveConfig({ projectId });
  const createRun = useCreateRun();
  const { data: modelProfile } = useModelProfile({ projectId });
  const { data: datasetProfile } = useDatasetProfile({ projectId });
  const { data: runs = [] } = useRuns({ projectId });

  const parsedConfig = React.useMemo((): WorkbenchConfig | null => {
    if (!configVersion?.yamlBlob) return null;
    try {
      return normalizeYamlConfig<WorkbenchConfig>(parseYaml(configVersion.yamlBlob));
    } catch {
      return null;
    }
  }, [configVersion]);

  const [slice, setSlice] = React.useState<TrainingFormSlice | null>(null);
  const [activeTab, setActiveTab] = React.useState<PageTab>("config");
  const [isYamlDialogOpen, setIsYamlDialogOpen] = React.useState(false);
  const [isLaunchDialogOpen, setIsLaunchDialogOpen] = React.useState(false);

  React.useEffect(() => {
    if (parsedConfig && !slice) {
      setSlice(sliceFromConfig(parsedConfig));
    }
  }, [parsedConfig, slice]);

  const trainingHistory = React.useMemo<ReadonlyArray<Run>>(() => {
    return [...runs].sort(
      (left, right) => new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime(),
    );
  }, [runs]);

  const runIds = React.useMemo<ReadonlyArray<string>>(
    () => trainingHistory.map((run) => run.id),
    [trainingHistory],
  );
  const { data: summaries } = useRunSummaries({ projectId, runIds });
  const summariesByRun = React.useMemo<ReadonlyMap<string, RunSummary>>(() => {
    const entries = new Map<string, RunSummary>();
    (summaries ?? []).forEach((summary) => entries.set(summary.runId, summary));
    return entries;
  }, [summaries]);

  const yamlPreview = React.useMemo<string>(() => {
    if (!parsedConfig || !slice) return "";
    const composed = composeFullConfig({ base: parsedConfig, slice });
    return stringifyYaml(denormalizeYamlConfig(composed));
  }, [parsedConfig, slice]);

  const handleSliceChange = React.useCallback((update: TrainingFormUpdate): void => {
    setSlice((current) => (current ? mergeSlice({ current, update }) : current));
  }, []);

  const handlePresetApply = (values: Partial<TrainingConfig>): void => {
    handleSliceChange({ training: values });
  };

  const handleSave = (): void => {
    if (!parsedConfig || !slice) return;
    const composed = composeFullConfig({ base: parsedConfig, slice });
    saveConfig.mutate(
      {
        request: {
          projectId,
          yamlContent: stringifyYaml(denormalizeYamlConfig(composed)),
          sourceTag: "user",
        },
      },
      {
        onSuccess: () => {
          toast({ title: "Config saved", description: "Training configuration saved." });
        },
        onError: () => {
          toast({
            title: "Save failed",
            description: "Failed to save training configuration.",
            variant: "destructive",
          });
        },
      },
    );
  };

  const launchWithConfigVersion = ({
    configVersionId,
    runName,
    savedNewVersion,
  }: {
    readonly configVersionId: string;
    readonly runName: string;
    readonly savedNewVersion: boolean;
  }): void => {
    createRun.mutate(
      { projectId, configVersionId },
      {
        onSuccess: () => {
          setIsLaunchDialogOpen(false);
          toast({
            title: "Run launched",
            description: `Started ${runName}.`,
          });
        },
        onError: (cause) => {
          const fallback = savedNewVersion
            ? "Config saved as a new version, but the run failed to start."
            : "Unable to start training run.";
          toast({
            title: "Launch failed",
            description: describeApiError({ cause, fallback }),
            variant: "destructive",
          });
        },
      },
    );
  };

  const handleLaunch = ({ runName }: { readonly runName: string }): void => {
    if (!configVersion || !parsedConfig || !slice) return;
    const composed = composeFullConfig({ base: parsedConfig, slice });
    const composedYaml = stringifyYaml(denormalizeYamlConfig(composed));

    if (composedYaml === configVersion.yamlBlob) {
      launchWithConfigVersion({
        configVersionId: configVersion.id,
        runName,
        savedNewVersion: false,
      });
      return;
    }

    saveConfig.mutate(
      {
        request: {
          projectId,
          yamlContent: composedYaml,
          sourceTag: "user",
        },
      },
      {
        onSuccess: (newVersion) => {
          launchWithConfigVersion({
            configVersionId: newVersion.id,
            runName,
            savedNewVersion: true,
          });
        },
        onError: (cause) => {
          toast({
            title: "Launch failed",
            description: describeApiError({
              cause,
              fallback: "Could not save config before launch.",
            }),
            variant: "destructive",
          });
        },
      },
    );
  };

  if (!activeProjectId) {
    return (
      <NoProjectSelected
        pageTitle="Training"
        description="Select a project on the Dashboard to configure its training settings."
      />
    );
  }

  return (
    <div className="flex flex-col gap-4 p-6">
      <header className="flex items-start justify-between gap-4">
        <div className="enter enter-1">
          <h1 className="font-mono text-[22px] font-semibold tracking-[-0.01em] text-ink-1">
            Training
          </h1>
          <p className="mt-1 font-mono text-[11px] text-ink-3">
            configure · schedule · launch runs
          </p>
        </div>
        <div className="flex items-center gap-2">
          {slice && parsedConfig ? (
            <CopyForAI
              buildPrompt={() =>
                buildTrainingPrompt({
                  training: slice.training,
                  optimization: slice.optimization,
                })
              }
            />
          ) : null}
          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsYamlDialogOpen(true)}
            disabled={!slice}
          >
            <FileText aria-hidden="true" />
            YAML
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleSave}
            disabled={!slice || saveConfig.isPending}
          >
            <Download aria-hidden="true" />
            {saveConfig.isPending ? "Saving…" : "Save config"}
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={() => setIsLaunchDialogOpen(true)}
            disabled={!configVersion || createRun.isPending || saveConfig.isPending}
          >
            <Play aria-hidden="true" />
            {createRun.isPending ? "Launching…" : "Launch run"}
          </Button>
        </div>
      </header>

      {isLoading ? <div className="font-mono text-[11px] text-ink-3">Loading config…</div> : null}
      {error ? (
        <div className="font-mono text-[11px] text-[color:var(--danger)]">
          Failed to load config.
        </div>
      ) : null}

      {slice ? (
        <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as PageTab)}>
          <TabsList>
            <TabsTrigger value="config">Config</TabsTrigger>
            <TabsTrigger value="schedule">Schedule</TabsTrigger>
            <TabsTrigger value="environment">Environment</TabsTrigger>
            <TabsTrigger value="history">History</TabsTrigger>
          </TabsList>

          <TabsContent value="config">
            <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1fr_260px]">
              <TrainingForm slice={slice} activeTab="config" onChange={handleSliceChange} />
              <TrainingPresetsPanel onApply={handlePresetApply} />
            </div>
          </TabsContent>

          <TabsContent value="schedule">
            <TrainingForm slice={slice} activeTab="schedule" onChange={handleSliceChange} />
          </TabsContent>

          <TabsContent value="environment">
            <TrainingForm slice={slice} activeTab="environment" onChange={handleSliceChange} />
          </TabsContent>

          <TabsContent value="history">
            <TrainingHistoryTab
              runs={trainingHistory}
              summariesByRun={summariesByRun}
              onRerun={() => setIsLaunchDialogOpen(true)}
            />
          </TabsContent>
        </Tabs>
      ) : null}

      <YamlPreviewDialog
        isOpen={isYamlDialogOpen}
        projectId={projectId}
        activeVersionId={configVersion?.id ?? null}
        yamlContent={yamlPreview}
        onClose={() => setIsYamlDialogOpen(false)}
      />
      {slice ? (
        <LaunchRunDialog
          isOpen={isLaunchDialogOpen}
          slice={slice}
          method={resolveMethod(slice)}
          modelId={modelProfile?.model_id ?? null}
          datasetId={datasetProfile?.datasetId ?? null}
          isLaunching={createRun.isPending || saveConfig.isPending}
          onLaunch={handleLaunch}
          onClose={() => setIsLaunchDialogOpen(false)}
        />
      ) : null}
    </div>
  );
}
