import * as React from "react";
import { useNavigate } from "react-router-dom";
import { GitCompare, Play } from "lucide-react";
import { useProjects } from "@/hooks/useProjects";
import { useSystemHealth } from "@/hooks/useSystemHealth";
import { useModelProfile } from "@/hooks/useModelProfile";
import { useDatasetProfile } from "@/hooks/useDatasetProfile";
import { useRuns, useRunMetrics } from "@/hooks/useRuns";
import { useRunStream } from "@/hooks/useRunStream";
import { useAppStore } from "@/stores/app-store";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ProjectSelector } from "@/components/dashboard/project-selector";
import { ResourceSnapshot } from "@/components/dashboard/resource-snapshot";
import { LatestRunStatusCard } from "@/components/dashboard/latest-run-status-card";
import { RecentRunsList } from "@/components/dashboard/recent-runs-list";
import { QuickLaunchActions } from "@/components/dashboard/quick-launch-actions";
import { StoragePanel } from "@/components/dashboard/storage-panel";
import { CurrentModelCard } from "@/components/dashboard/current-model-card";
import { CurrentDatasetCard } from "@/components/dashboard/current-dataset-card";
import { PipelineCard } from "@/components/dashboard/pipeline-card";
import { DashboardMetricsRow } from "@/components/dashboard/dashboard-metrics-row";
import type { Run } from "@/types/run";

function pickActiveRun(runs: ReadonlyArray<Run>): Run | null {
  return (
    runs.find(
      (run) => run.status === "running" || run.status === "pending" || run.status === "paused",
    ) ?? null
  );
}

export default function DashboardPage(): React.JSX.Element {
  const navigate = useNavigate();
  const { data: projects = [] } = useProjects();
  const { data: systemHealth } = useSystemHealth();
  const { activeProjectId, setActiveProjectId } = useAppStore();

  const projectId = activeProjectId ?? "";
  const { data: modelProfile, isLoading: isLoadingModel } = useModelProfile({ projectId });
  const { data: datasetProfile, isLoading: isLoadingDataset } = useDatasetProfile({ projectId });
  const { data: runs = [] } = useRuns({ projectId });

  const activeRun = React.useMemo(() => pickActiveRun(runs), [runs]);
  const activeRunId = activeRun?.id ?? null;

  const streamState = useRunStream({
    projectId: activeProjectId,
    runId: activeRunId,
  });
  const { data: historicalMetrics = [] } = useRunMetrics({
    projectId,
    runId: activeRunId ?? "",
  });

  const handleProjectSelect = (selectedId: string): void => {
    setActiveProjectId(selectedId);
  };

  return (
    <div className="flex flex-col gap-6 p-6">
      <header className="flex items-start justify-between gap-4">
        <div className="enter enter-1">
          <h1 className="font-mono text-[22px] font-semibold tracking-[-0.01em] text-ink-1">
            Workbench
          </h1>
          <p className="mt-1 font-mono text-[11px] text-ink-3">
            project · {activeProjectId ? projectId : "none"} · dashboard
          </p>
        </div>
        <div className="flex items-center gap-2">
          <ProjectSelector
            projects={projects}
            selectedProjectId={activeProjectId}
            onSelect={handleProjectSelect}
          />
          <Button variant="outline" size="sm" onClick={() => void navigate("/compare")}>
            <GitCompare aria-hidden="true" />
            Compare
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={() => void navigate("/training")}
            disabled={!activeProjectId}
          >
            <Play aria-hidden="true" />
            Start run
          </Button>
        </div>
      </header>

      {!activeProjectId ? (
        <Card>
          <CardContent className="py-10 text-center font-mono text-[11px] text-ink-3">
            Select a project to see its status and recent activity.
          </CardContent>
        </Card>
      ) : (
        <>
          {activeRun ? (
            <div className="enter enter-2">
              <LatestRunStatusCard
                run={activeRun}
                currentStep={streamState.currentStep}
                totalSteps={streamState.totalSteps}
                progressPct={streamState.progressPct}
              />
            </div>
          ) : null}

          <div className="enter enter-3">
            <DashboardMetricsRow
              runs={runs}
              liveMetrics={streamState.liveMetrics}
              historicalMetrics={historicalMetrics}
            />
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-[2fr_1fr]">
            <div className="flex flex-col gap-6">
              <div className="enter enter-4">
                <PipelineCard runs={runs} />
              </div>
              <div className="enter enter-5">
                <RecentRunsList runs={runs} />
              </div>
              <div className="enter enter-6">
                <QuickLaunchActions hasActiveProject={Boolean(activeProjectId)} />
              </div>
            </div>
            <div className="flex flex-col gap-6">
              {systemHealth ? (
                <div className="enter enter-5">
                  <ResourceSnapshot health={systemHealth} />
                </div>
              ) : null}
              <div className="enter enter-6">
                <CurrentModelCard profile={modelProfile} isLoading={isLoadingModel} />
              </div>
              <div className="enter enter-7">
                <CurrentDatasetCard profile={datasetProfile} isLoading={isLoadingDataset} />
              </div>
              <div className="enter enter-8">
                <StoragePanel projectId={activeProjectId} />
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
