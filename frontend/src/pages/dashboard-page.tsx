import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { useProjects } from "@/hooks/useProjects";
import { useSystemHealth } from "@/hooks/useSystemHealth";
import { useModelProfile } from "@/hooks/useModelProfile";
import { useDatasetProfile } from "@/hooks/useDatasetProfile";
import { useAppStore } from "@/stores/app-store";
import { fetchApi } from "@/api/client";
import { ProjectSelector } from "@/components/dashboard/project-selector";
import { ResourceSnapshot } from "@/components/dashboard/resource-snapshot";
import { LatestRunStatusCard } from "@/components/dashboard/latest-run-status-card";
import { RecentRunsList } from "@/components/dashboard/recent-runs-list";
import { QuickLaunchActions } from "@/components/dashboard/quick-launch-actions";
import { StoragePanel } from "@/components/dashboard/storage-panel";
import { CurrentModelCard } from "@/components/dashboard/current-model-card";
import { CurrentDatasetCard } from "@/components/dashboard/current-dataset-card";
import { RecentConfigChanges } from "@/components/dashboard/recent-config-changes";
import type { RawConfigVersionItem } from "@/components/dashboard/recent-config-changes";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface RawConfigVersionListResponse {
  readonly items: ReadonlyArray<RawConfigVersionItem>;
  readonly total: number;
}

export default function DashboardPage(): React.JSX.Element {
  const { data: projects } = useProjects();
  const { data: systemHealth } = useSystemHealth();
  const { activeProjectId, setActiveProjectId } = useAppStore();

  const projectId = activeProjectId ?? "";

  const { data: modelProfile, isLoading: isLoadingModel } = useModelProfile({
    projectId,
  });
  const { data: datasetProfile, isLoading: isLoadingDataset } = useDatasetProfile({
    projectId,
  });
  const { data: configVersionsList, isLoading: isLoadingConfigs } =
    useQuery<RawConfigVersionListResponse>({
      queryKey: ["projects", projectId, "configs", "list"],
      queryFn: () =>
        fetchApi<RawConfigVersionListResponse>({
          path: `/projects/${projectId}/configs?limit=5`,
        }),
      enabled: Boolean(projectId),
    });

  const handleProjectSelect = (selectedId: string): void => {
    setActiveProjectId(selectedId);
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Dashboard</h1>
        <ProjectSelector
          projects={projects ?? []}
          selectedProjectId={activeProjectId}
          onSelect={handleProjectSelect}
        />
      </div>

      {!activeProjectId && (
        <Card>
          <CardContent className="py-8 text-center text-sm text-muted-foreground">
            Select a project to see its status and recent activity.
          </CardContent>
        </Card>
      )}

      {activeProjectId && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          <LatestRunStatusCard run={null} />

          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Recent Runs</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <RecentRunsList runs={[]} />
            </CardContent>
          </Card>

          {systemHealth && <ResourceSnapshot health={systemHealth} />}

          <StoragePanel projectId={activeProjectId} />

          <CurrentModelCard profile={modelProfile} isLoading={isLoadingModel} />

          <CurrentDatasetCard profile={datasetProfile} isLoading={isLoadingDataset} />

          <RecentConfigChanges
            items={configVersionsList?.items ?? []}
            isLoading={isLoadingConfigs}
          />

          <Card className="md:col-span-2 xl:col-span-3">
            <CardHeader>
              <CardTitle className="text-sm">Quick Launch</CardTitle>
            </CardHeader>
            <CardContent>
              <QuickLaunchActions hasActiveProject={Boolean(activeProjectId)} />
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
