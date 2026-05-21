import * as React from "react";
import { parse as parseYaml, stringify as stringifyYaml } from "yaml";
import { GitCompare, Play } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useAppStore } from "@/stores/app-store";
import { useRunStreamStore } from "@/stores/run-stream-store";
import { denormalizeYamlConfig, normalizeYamlConfig } from "@/lib/yaml-config";
import type { DataPolicy, SaveConfigRequest, WorkbenchConfig } from "@/types/config";
import {
  useCancelRun,
  useCheckpoints,
  useCreateRun,
  useDeleteRun,
  usePauseRun,
  useResumeRun,
  useRunLogs,
  useRunMetrics,
  useRunStages,
  useRuns,
} from "@/hooks/useRuns";
import { useActiveConfig, useSaveConfig } from "@/hooks/useConfigs";
import { useSettings } from "@/hooks/useSettings";
import { useRunStream } from "@/hooks/useRunStream";
import { useToast } from "@/hooks/use-toast";
import { describeApiError } from "@/lib/api-error";
import { ActiveRunBanner } from "@/components/runs/active-run-banner";
import { CheckpointList } from "@/components/runs/checkpoint-list";
import { ConfigSnapshotTab } from "@/components/runs/config-snapshot-tab";
import { EnvironmentSelector } from "@/components/runs/environment-selector";
import { FailurePanel } from "@/components/runs/failure-panel";
import { LiveMetricsCharts } from "@/components/runs/live-metrics-charts";
import { LogStream } from "@/components/runs/log-stream";
import { ResumeFromCheckpointDialog } from "@/components/runs/resume-from-checkpoint-dialog";
import { RunActions } from "@/components/runs/run-actions";
import { RunAttemptsStrip } from "@/components/runs/run-attempts-strip";
import { RunFallbackDialog } from "@/components/runs/run-fallback-dialog";
import { RunList } from "@/components/runs/run-list";
import { RunTimeline } from "@/components/runs/run-timeline";
import { StageDetailPanel } from "@/components/runs/stage-detail-panel";
import { SystemResourceMonitor } from "@/components/runs/system-resource-monitor";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { RangePills } from "@/components/shared/range-pills";
import { StatusDot } from "@/components/shared/status-dot";
import type { Checkpoint, ModalGpuType, Run, TrainingEnvironment } from "@/types/run";

type StatusFilter = "all" | "running" | "success" | "failed" | "paused";

const STATUS_FILTER_OPTIONS = [
  { value: "all" as StatusFilter, label: "All" },
  { value: "running" as StatusFilter, label: "Running" },
  { value: "success" as StatusFilter, label: "Success" },
  { value: "failed" as StatusFilter, label: "Failed" },
  { value: "paused" as StatusFilter, label: "Paused" },
];

function statusMatches({
  run,
  filter,
}: {
  readonly run: Run;
  readonly filter: StatusFilter;
}): boolean {
  switch (filter) {
    case "all":
      return true;
    case "running":
      return run.status === "running" || run.status === "pending";
    case "success":
      return run.status === "completed";
    case "failed":
      return run.status === "failed" || run.status === "cancelled";
    case "paused":
      return run.status === "paused";
    default: {
      const _exhaustive: never = filter;
      return _exhaustive;
    }
  }
}

function pickLiveRun(runs: ReadonlyArray<Run>): Run | null {
  return (
    runs.find(
      (run) =>
        run.status === "running" ||
        run.status === "pending" ||
        run.status === "paused" ||
        run.status === "fallback_pending",
    ) ?? null
  );
}

function countByStatus(runs: ReadonlyArray<Run>, predicate: (run: Run) => boolean): number {
  let total = 0;
  for (const run of runs) if (predicate(run)) total += 1;
  return total;
}

interface MaybeCreateOverrideParams {
  readonly projectId: string;
  readonly activeConfig: { readonly id: string; readonly yamlBlob: string };
  readonly environment: TrainingEnvironment;
  readonly modalGpuType: ModalGpuType | null;
  readonly saveConfig: (params: {
    readonly request: SaveConfigRequest;
  }) => Promise<{ readonly id: string }>;
}

export async function maybeCreateOverrideConfig({
  projectId,
  activeConfig,
  environment,
  modalGpuType,
  saveConfig,
}: MaybeCreateOverrideParams): Promise<string | null> {
  const parsed = normalizeYamlConfig<WorkbenchConfig>(parseYaml(activeConfig.yamlBlob));
  const currentEnv = parsed.execution.environment;
  const currentGpu = parsed.execution.modalGpuType;
  const currentDataPolicy = parsed.execution.dataPolicy;
  // Backend ExecutionConfig.modal_gpu_type is a non-nullable Literal with
  // default "a10"; serializing null would invalidate the config. When the
  // target environment is local, preserve the existing GPU (or fall back to
  // the same default the backend would apply) so the field stays valid.
  const targetGpu: ModalGpuType =
    environment === "modal" && modalGpuType !== null ? modalGpuType : (currentGpu ?? "a10");
  // Backend _validate_execution_for_run rejects modal + local_raw outright.
  // When the picker promotes a local config to modal, force the cloud policy
  // so the launch survives validation; when reverting to local, leave the
  // saved policy alone (local_raw is the local-default).
  const targetDataPolicy: DataPolicy =
    environment === "modal" ? "sanitized_cloud" : (currentDataPolicy ?? "local_raw");
  const envChanged = currentEnv !== environment;
  const gpuChanged = environment === "modal" && currentGpu !== targetGpu;
  const dataPolicyChanged = currentDataPolicy !== targetDataPolicy;
  if (!envChanged && !gpuChanged && !dataPolicyChanged) {
    return null;
  }
  const patched: WorkbenchConfig = {
    ...parsed,
    execution: {
      ...parsed.execution,
      environment,
      modalGpuType: targetGpu,
      dataPolicy: targetDataPolicy,
    },
  };
  const patchedYaml = stringifyYaml(denormalizeYamlConfig(patched));
  const newVersion = await saveConfig({
    request: {
      projectId,
      yamlContent: patchedYaml,
      sourceTag: "user",
      sourceDetail: "runs-page environment override",
    },
  });
  return newVersion.id;
}

export default function RunsPage(): React.JSX.Element {
  const navigate = useNavigate();
  const { toast } = useToast();
  const { activeProjectId } = useAppStore();
  const [selectedRunId, setSelectedRunId] = React.useState<string | null>(null);
  const [selectedStageId, setSelectedStageId] = React.useState<string | null>(null);
  const [isResumeDialogOpen, setIsResumeDialogOpen] = React.useState(false);
  const [environment, setEnvironment] = React.useState<TrainingEnvironment>("local");
  const [modalGpuType, setModalGpuType] = React.useState<ModalGpuType | null>(null);
  const [statusFilter, setStatusFilter] = React.useState<StatusFilter>("all");

  const { data: settings } = useSettings();
  const isModalTokenSet = settings?.isModalTokenSet ?? false;

  const { data: runs = [], isLoading: isRunsLoading } = useRuns({
    projectId: activeProjectId ?? "",
  });

  const filteredRuns = React.useMemo(
    () => runs.filter((run) => statusMatches({ run, filter: statusFilter })),
    [runs, statusFilter],
  );

  const selectedRun = React.useMemo(
    () => runs.find((run) => run.id === selectedRunId) ?? null,
    [runs, selectedRunId],
  );

  const { data: stages = [] } = useRunStages({
    projectId: activeProjectId ?? "",
    runId: selectedRunId ?? "",
  });

  const { data: checkpoints = [] } = useCheckpoints({
    projectId: activeProjectId ?? "",
    runId: selectedRunId ?? "",
  });

  const streamState = useRunStream({
    projectId: activeProjectId,
    runId: selectedRunId,
  });

  const { data: historicalMetrics = [] } = useRunMetrics({
    projectId: activeProjectId ?? "",
    runId: selectedRunId ?? "",
  });

  const { data: historicalLogsResponse } = useRunLogs({
    projectId: activeProjectId ?? "",
    runId: selectedRunId ?? "",
  });

  const historicalLogs = historicalLogsResponse?.logs ?? [];

  const mergedMetrics = React.useMemo(() => {
    const seen = new Set<string>();
    return [...historicalMetrics, ...streamState.liveMetrics].filter((point) => {
      const key = `${point.step}:${point.metricName}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }, [historicalMetrics, streamState.liveMetrics]);

  const mergedLogs = React.useMemo(() => {
    const seen = new Set<string>();
    return [...historicalLogs, ...streamState.liveLogs].filter((entry) => {
      const key = `${entry.timestamp}:${entry.message}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }, [historicalLogs, streamState.liveLogs]);

  const cancelRun = useCancelRun();
  const deleteRunMutation = useDeleteRun();
  const pauseRun = usePauseRun();
  const resumeRun = useResumeRun();
  const createRunMutation = useCreateRun();

  const { data: activeConfig } = useActiveConfig({ projectId: activeProjectId ?? "" });
  const saveConfig = useSaveConfig({ projectId: activeProjectId ?? "" });

  const { fallbackProposal, clearFallbackProposal } = useRunStreamStore((state) => ({
    fallbackProposal: selectedRunId ? (state.fallbackProposals[selectedRunId] ?? null) : null,
    clearFallbackProposal: state.clearFallbackProposal,
  }));

  const maxRunMinutes = React.useMemo<number>(() => {
    if (!activeConfig?.yamlBlob) return 90;
    try {
      const parsed = normalizeYamlConfig<WorkbenchConfig>(parseYaml(activeConfig.yamlBlob));
      return parsed.execution?.maxRunMinutes ?? 90;
    } catch {
      return 90;
    }
  }, [activeConfig]);

  const liveRun = React.useMemo(() => pickLiveRun(runs), [runs]);
  const canStartRun = Boolean(activeConfig) && liveRun === null;

  React.useEffect(() => {
    if (!activeConfig?.yamlBlob) return;
    try {
      const parsed = normalizeYamlConfig<WorkbenchConfig>(parseYaml(activeConfig.yamlBlob));
      const configuredEnv = parsed.execution?.environment;
      const configuredGpu = parsed.execution?.modalGpuType ?? null;
      if (configuredEnv === "local" || configuredEnv === "modal") {
        setEnvironment(configuredEnv);
      }
      setModalGpuType(configuredGpu);
    } catch {
      // Malformed config — leave the picker at its current value rather than
      // forcing it to the local default and creating a silent override on Start.
    }
  }, [activeConfig?.id, activeConfig?.yamlBlob]);

  React.useEffect(() => {
    if (liveRun && !selectedRunId) {
      setSelectedRunId(liveRun.id);
    } else if (!selectedRunId && runs.length > 0) {
      setSelectedRunId(runs[0].id);
    }
  }, [liveRun, selectedRunId, runs]);

  const selectedStage = stages.find((stage) => stage.id === selectedStageId) ?? null;

  const allCheckpoints: ReadonlyArray<Checkpoint> = [
    ...checkpoints,
    ...streamState.liveCheckpoints,
  ];

  const totalRunCount = runs.length;
  const streamingCount = countByStatus(runs, (run) => run.status === "running");
  const pausedCount = countByStatus(runs, (run) => run.status === "paused");

  const handleStartRun = async (): Promise<void> => {
    if (!activeProjectId || !activeConfig) return;
    if (environment === "modal" && modalGpuType === null) {
      toast({
        title: "Pick a GPU first",
        description: "Modal runs require a GPU tier.",
        variant: "destructive",
      });
      return;
    }

    let configVersionId = activeConfig.id;
    try {
      const overrideId = await maybeCreateOverrideConfig({
        projectId: activeProjectId,
        activeConfig,
        environment,
        modalGpuType,
        saveConfig: saveConfig.mutateAsync,
      });
      if (overrideId !== null) {
        configVersionId = overrideId;
      }
    } catch (cause) {
      toast({
        title: "Could not prepare config override",
        description: describeApiError({ cause, fallback: "Failed to save config override." }),
        variant: "destructive",
      });
      return;
    }

    createRunMutation.mutate(
      { projectId: activeProjectId, configVersionId },
      {
        onSuccess: (newRun) => {
          setSelectedRunId(newRun.id);
          setSelectedStageId(null);
          toast({
            title: "Run launched",
            description: `Started run ${newRun.id.slice(0, 6)}.`,
          });
        },
        onError: (cause) => {
          toast({
            title: "Launch failed",
            description: describeApiError({ cause, fallback: "Unknown error." }),
            variant: "destructive",
          });
        },
      },
    );
  };

  const handleDeleteRun = (runId: string): void => {
    if (!activeProjectId) return;
    deleteRunMutation.mutate(
      { projectId: activeProjectId, runId },
      {
        onSuccess: () => {
          if (selectedRunId === runId) {
            setSelectedRunId(null);
            setSelectedStageId(null);
          }
          toast({
            title: "Run deleted",
            description: `Deleted run ${runId.slice(0, 6)}.`,
          });
        },
        onError: (cause) => {
          toast({
            title: "Delete failed",
            description: describeApiError({ cause, fallback: "Unknown error." }),
            variant: "destructive",
          });
        },
      },
    );
  };

  const handleCancelSelected = (): void => {
    if (!activeProjectId || !selectedRunId) return;
    cancelRun.mutate({ projectId: activeProjectId, runId: selectedRunId });
  };

  const handlePauseSelected = (): void => {
    if (!activeProjectId || !selectedRunId) return;
    pauseRun.mutate({ projectId: activeProjectId, runId: selectedRunId });
  };

  const handleResumeSelected = (): void => {
    if (allCheckpoints.length === 0) {
      if (!activeProjectId || !selectedRunId) return;
      resumeRun.mutate({ projectId: activeProjectId, runId: selectedRunId });
    } else {
      setIsResumeDialogOpen(true);
    }
  };

  const handleResumeFromCheckpoint = (_checkpoint: Checkpoint): void => {
    if (!activeProjectId || !selectedRunId) return;
    resumeRun.mutate(
      { projectId: activeProjectId, runId: selectedRunId },
      { onSuccess: () => setIsResumeDialogOpen(false) },
    );
  };

  if (!activeProjectId) {
    return (
      <div className="p-6">
        <h1 className="font-mono text-[22px] font-semibold text-ink-1">Runs</h1>
        <p className="mt-2 font-mono text-[11px] text-ink-3">Select a project to view runs.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 p-6">
      <header className="flex items-start justify-between gap-4">
        <div className="enter enter-1">
          <h1 className="font-mono text-[22px] font-semibold tracking-[-0.01em] text-ink-1">
            Runs
          </h1>
          <div className="mt-1 flex flex-wrap items-center gap-4 font-mono text-[11px] text-ink-3">
            <span>
              <span className="text-ink-1">{totalRunCount}</span> total
            </span>
            <span className="inline-flex items-center gap-1.5">
              <StatusDot status="running" />
              <span className="text-ink-1">{streamingCount}</span> streaming
            </span>
            <span className="inline-flex items-center gap-1.5">
              <StatusDot status="paused" />
              <span className="text-ink-1">{pausedCount}</span> paused
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => void navigate("/compare")}>
            <GitCompare aria-hidden="true" />
            Compare
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={() => {
              void handleStartRun();
            }}
            disabled={!canStartRun || createRunMutation.isPending}
          >
            <Play aria-hidden="true" />
            {createRunMutation.isPending ? "Starting…" : "Start run"}
          </Button>
        </div>
      </header>

      <div className="flex flex-wrap items-center gap-3 rounded-md border border-hairline bg-surface-2 px-3 py-2 enter enter-2">
        <EnvironmentSelector
          environment={environment}
          onEnvironmentChange={setEnvironment}
          modalGpuType={modalGpuType}
          onModalGpuTypeChange={setModalGpuType}
          isModalTokenSet={isModalTokenSet}
        />
        <span className="h-4 w-px bg-hairline" aria-hidden="true" />
        <RangePills
          options={STATUS_FILTER_OPTIONS}
          value={statusFilter}
          onChange={setStatusFilter}
          ariaLabel="Status filter"
        />
        {selectedRun ? (
          <div className="ml-auto">
            <RunActions
              run={selectedRun}
              onCancel={handleCancelSelected}
              onPause={handlePauseSelected}
              onResume={handleResumeSelected}
              isCancelling={cancelRun.isPending}
              isPausing={pauseRun.isPending}
              isResuming={resumeRun.isPending}
            />
          </div>
        ) : null}
      </div>

      {liveRun && selectedRunId === liveRun.id ? (
        <div className="enter enter-3">
          <ActiveRunBanner
            run={liveRun}
            currentStep={streamState.currentStep}
            totalSteps={streamState.totalSteps}
            progressPct={streamState.progressPct}
            isConnected={streamState.isConnected}
            onPause={liveRun.status === "running" ? handlePauseSelected : undefined}
            onResume={liveRun.status === "paused" ? handleResumeSelected : undefined}
            onStop={handleCancelSelected}
          />
        </div>
      ) : null}

      {isRunsLoading ? (
        <div className="font-mono text-[11px] text-ink-3">Loading runs…</div>
      ) : (
        <div className="enter enter-4">
          <RunList
            runs={filteredRuns}
            selectedRunId={selectedRunId}
            onSelectRun={(id) => {
              setSelectedRunId(id);
              setSelectedStageId(null);
            }}
            onDeleteRun={handleDeleteRun}
            isDeletingRunId={
              deleteRunMutation.isPending ? (deleteRunMutation.variables?.runId ?? null) : null
            }
            onStartRun={() => {
              void handleStartRun();
            }}
            isStartingRun={createRunMutation.isPending}
            canStartRun={canStartRun}
          />
        </div>
      )}

      {selectedRun ? (
        <>
          {selectedRun.status === "failed" ? <FailurePanel run={selectedRun} /> : null}
          {selectedRun.attempts.length > 1 ? (
            <RunAttemptsStrip attempts={selectedRun.attempts} />
          ) : null}
          <Tabs defaultValue="timeline" className="mt-2">
            <TabsList>
              <TabsTrigger value="timeline">Timeline</TabsTrigger>
              <TabsTrigger value="metrics">Metrics</TabsTrigger>
              <TabsTrigger value="logs">Logs</TabsTrigger>
              <TabsTrigger value="system">System</TabsTrigger>
              <TabsTrigger value="config">Config</TabsTrigger>
              <TabsTrigger value="ckpts">
                Checkpoints
                {allCheckpoints.length > 0 ? (
                  <Badge variant="secondary" dot={false} className="ml-1">
                    {allCheckpoints.length}
                  </Badge>
                ) : null}
              </TabsTrigger>
            </TabsList>

            <TabsContent value="timeline" className="space-y-3">
              <RunTimeline
                stages={stages}
                selectedStageId={selectedStageId}
                onSelectStage={setSelectedStageId}
              />
              {selectedStage ? (
                <StageDetailPanel stage={selectedStage} onClose={() => setSelectedStageId(null)} />
              ) : null}
            </TabsContent>

            <TabsContent value="metrics">
              <LiveMetricsCharts
                projectId={activeProjectId ?? ""}
                runId={selectedRun.id}
                metricPoints={mergedMetrics}
              />
            </TabsContent>

            <TabsContent value="logs">
              <LogStream logs={mergedLogs} />
            </TabsContent>

            <TabsContent value="system">
              <SystemResourceMonitor resources={streamState.systemResources} />
            </TabsContent>

            <TabsContent value="config" className="space-y-3">
              {activeProjectId && selectedRunId ? (
                <ConfigSnapshotTab projectId={activeProjectId} runId={selectedRunId} />
              ) : (
                <div className="text-xs text-muted-foreground">
                  Select a run to view its config.
                </div>
              )}
            </TabsContent>

            <TabsContent value="ckpts">
              <CheckpointList
                checkpoints={allCheckpoints}
                selectedCheckpointPath={null}
                onSelectCheckpoint={() => setIsResumeDialogOpen(true)}
              />
            </TabsContent>
          </Tabs>
        </>
      ) : null}

      <ResumeFromCheckpointDialog
        isOpen={isResumeDialogOpen}
        checkpoints={allCheckpoints}
        onConfirm={handleResumeFromCheckpoint}
        onClose={() => setIsResumeDialogOpen(false)}
        isResuming={resumeRun.isPending}
      />

      {activeProjectId && selectedRunId ? (
        <RunFallbackDialog
          isOpen={fallbackProposal !== null}
          projectId={activeProjectId}
          runId={selectedRunId}
          maxRunMinutes={maxRunMinutes}
          proposal={fallbackProposal}
          onClose={() => {
            if (selectedRunId) clearFallbackProposal(selectedRunId);
          }}
        />
      ) : null}
    </div>
  );
}
