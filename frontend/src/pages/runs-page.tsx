import * as React from "react";
import { useAppStore } from "@/stores/app-store";
import {
  useRuns,
  useRunStages,
  useRunMetrics,
  useRunLogs,
  useCheckpoints,
  useCancelRun,
  useDeleteRun,
  usePauseRun,
  useResumeRun,
  useCreateRun,
} from "@/hooks/useRuns";
import { useActiveConfig } from "@/hooks/useConfigs";
import { useSettings } from "@/hooks/useSettings";
import { useRunStream } from "@/hooks/useRunStream";
import { RunList } from "@/components/runs/run-list";
import { EnvironmentSelector } from "@/components/runs/environment-selector";
import { Button } from "@/components/ui/button";
import { ActiveRunBanner } from "@/components/runs/active-run-banner";
import { RunTimeline } from "@/components/runs/run-timeline";
import { StageDetailPanel } from "@/components/runs/stage-detail-panel";
import { LiveMetricsCharts } from "@/components/runs/live-metrics-charts";
import { LogStream } from "@/components/runs/log-stream";
import { SystemResourceMonitor } from "@/components/runs/system-resource-monitor";
import { CheckpointList } from "@/components/runs/checkpoint-list";
import { FailurePanel } from "@/components/runs/failure-panel";
import { RunActions } from "@/components/runs/run-actions";
import { ResumeFromCheckpointDialog } from "@/components/runs/resume-from-checkpoint-dialog";
import type { AppSettings } from "@/types/settings";
import type { Checkpoint, TrainingEnvironment, ModalGpuType } from "@/types/run";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

type SettingsWithModal = AppSettings & { readonly isModalTokenSet?: boolean };

export default function RunsPage(): React.JSX.Element {
  const { activeProjectId } = useAppStore();
  const [selectedRunId, setSelectedRunId] = React.useState<string | null>(null);
  const [selectedStageId, setSelectedStageId] = React.useState<string | null>(null);
  const [isResumeDialogOpen, setIsResumeDialogOpen] = React.useState(false);
  const [environment, setEnvironment] = React.useState<TrainingEnvironment>("local");
  const [modalGpuType, setModalGpuType] = React.useState<ModalGpuType | null>(null);

  const { data: settings } = useSettings();
  // isModalTokenSet is added by the settings-builder branch; optional until merged
  const isModalTokenSet = (settings as SettingsWithModal | undefined)?.isModalTokenSet ?? false;

  const { data: runs = [], isLoading: isRunsLoading } = useRuns({
    projectId: activeProjectId ?? "",
  });

  const selectedRun = runs.find((r) => r.id === selectedRunId) ?? null;

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
    return [...historicalMetrics, ...streamState.liveMetrics].filter((p) => {
      const key = `${p.step}:${p.metricName}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }, [historicalMetrics, streamState.liveMetrics]);

  const mergedLogs = React.useMemo(() => {
    const seen = new Set<string>();
    return [...historicalLogs, ...streamState.liveLogs].filter((l) => {
      const key = `${l.timestamp}:${l.message}`;
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

  const activeRun = runs.find((r) => r.status === "running" || r.status === "pending") ?? null;
  const canStartRun = Boolean(activeConfig) && !activeRun;

  React.useEffect(() => {
    if (activeRun && !selectedRunId) {
      setSelectedRunId(activeRun.id);
    }
  }, [activeRun, selectedRunId]);
  const selectedStage = stages.find((s) => s.id === selectedStageId) ?? null;

  const allCheckpoints: ReadonlyArray<Checkpoint> = [
    ...checkpoints,
    ...streamState.liveCheckpoints,
  ];

  const handleStartRun = (): void => {
    if (!activeProjectId || !activeConfig) return;
    createRunMutation.mutate(
      { projectId: activeProjectId, configVersionId: activeConfig.id },
      { onSuccess: (newRun) => setSelectedRunId(newRun.id) },
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
        },
      },
    );
  };

  const handleCancelRun = (): void => {
    if (!activeProjectId || !selectedRunId) return;
    cancelRun.mutate({ projectId: activeProjectId, runId: selectedRunId });
  };

  const handlePauseRun = (): void => {
    if (!activeProjectId || !selectedRunId) return;
    pauseRun.mutate({ projectId: activeProjectId, runId: selectedRunId });
  };

  const handleResumeRun = (): void => {
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
        <h1 className="text-xl font-semibold mb-2">Runs</h1>
        <p className="text-sm text-muted-foreground">Select a project to view runs.</p>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-xl font-semibold shrink-0">Runs</h1>
        <div className="flex items-center gap-3 flex-wrap">
          <EnvironmentSelector
            environment={environment}
            onEnvironmentChange={setEnvironment}
            modalGpuType={modalGpuType}
            onModalGpuTypeChange={setModalGpuType}
            isModalTokenSet={isModalTokenSet}
          />
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              onClick={handleStartRun}
              disabled={!canStartRun || createRunMutation.isPending}
            >
              {createRunMutation.isPending ? "Starting…" : "Start Run"}
            </Button>
            {selectedRun && (
              <RunActions
                run={selectedRun}
                onCancel={handleCancelRun}
                onPause={handlePauseRun}
                onResume={handleResumeRun}
                isCancelling={cancelRun.isPending}
                isPausing={pauseRun.isPending}
                isResuming={resumeRun.isPending}
              />
            )}
          </div>
        </div>
      </div>

      {activeRun && selectedRunId === activeRun.id && (
        <ActiveRunBanner
          run={activeRun}
          currentStep={streamState.currentStep}
          totalSteps={streamState.totalSteps}
          progressPct={streamState.progressPct}
          isConnected={streamState.isConnected}
        />
      )}

      {isRunsLoading && <div className="text-sm text-muted-foreground">Loading runs…</div>}

      {!isRunsLoading && (
        <RunList
          runs={runs}
          selectedRunId={selectedRunId}
          onSelectRun={(id) => {
            setSelectedRunId(id);
            setSelectedStageId(null);
          }}
          onDeleteRun={handleDeleteRun}
          isDeletingRunId={
            deleteRunMutation.isPending ? (deleteRunMutation.variables?.runId ?? null) : null
          }
          onStartRun={handleStartRun}
          isStartingRun={createRunMutation.isPending}
          canStartRun={canStartRun}
        />
      )}

      {selectedRun && (
        <>
          {selectedRun.status === "failed" && <FailurePanel run={selectedRun} />}

          <Tabs defaultValue="timeline">
            <TabsList>
              <TabsTrigger value="timeline">Timeline</TabsTrigger>
              <TabsTrigger value="metrics">Metrics</TabsTrigger>
              <TabsTrigger value="logs">Logs</TabsTrigger>
              <TabsTrigger value="system">System</TabsTrigger>
              <TabsTrigger value="checkpoints">Checkpoints</TabsTrigger>
            </TabsList>

            <TabsContent value="timeline" className="mt-4 space-y-3">
              <RunTimeline
                stages={stages}
                selectedStageId={selectedStageId}
                onSelectStage={setSelectedStageId}
              />
              {selectedStage && (
                <StageDetailPanel stage={selectedStage} onClose={() => setSelectedStageId(null)} />
              )}
            </TabsContent>

            <TabsContent value="metrics" className="mt-4">
              <LiveMetricsCharts metricPoints={mergedMetrics} />
            </TabsContent>

            <TabsContent value="logs" className="mt-4 h-96">
              <LogStream logs={mergedLogs} />
            </TabsContent>

            <TabsContent value="system" className="mt-4">
              <SystemResourceMonitor resources={streamState.systemResources} />
            </TabsContent>

            <TabsContent value="checkpoints" className="mt-4">
              <CheckpointList
                checkpoints={allCheckpoints}
                selectedCheckpointPath={null}
                onSelectCheckpoint={() => setIsResumeDialogOpen(true)}
              />
            </TabsContent>
          </Tabs>
        </>
      )}

      <ResumeFromCheckpointDialog
        isOpen={isResumeDialogOpen}
        checkpoints={allCheckpoints}
        onConfirm={handleResumeFromCheckpoint}
        onClose={() => setIsResumeDialogOpen(false)}
        isResuming={resumeRun.isPending}
      />
    </div>
  );
}
