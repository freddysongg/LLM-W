import * as React from "react";
import { useProjects } from "@/hooks/useProjects";
import { useSystemHealth } from "@/hooks/useSystemHealth";
import { useAppStore } from "@/stores/app-store";
import { ProjectSelector } from "@/components/dashboard/project-selector";
import { ResourceSnapshot } from "@/components/dashboard/resource-snapshot";
import { LatestRunStatusCard } from "@/components/dashboard/latest-run-status-card";
import { RecentRunsList } from "@/components/dashboard/recent-runs-list";
import { QuickLaunchActions } from "@/components/dashboard/quick-launch-actions";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function DashboardPage(): React.JSX.Element {
  const { data: projects } = useProjects();
  const { data: systemHealth } = useSystemHealth();
  const { activeProjectId, setActiveProjectId } = useAppStore();

  const handleProjectSelect = (projectId: string): void => {
    setActiveProjectId(projectId);
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
