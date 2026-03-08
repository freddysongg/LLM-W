import * as React from "react";
import { useNavigate } from "react-router-dom";
import { Play, Settings, BarChart2 } from "lucide-react";
import { Button } from "@/components/ui/button";

interface QuickLaunchActionsProps {
  readonly hasActiveProject: boolean;
}

export function QuickLaunchActions({
  hasActiveProject,
}: QuickLaunchActionsProps): React.JSX.Element {
  const navigate = useNavigate();

  return (
    <div className="flex gap-2 flex-wrap">
      <Button size="sm" disabled={!hasActiveProject} onClick={() => void navigate("/runs")}>
        <Play className="h-4 w-4 mr-1" />
        New Run
      </Button>
      <Button
        size="sm"
        variant="outline"
        disabled={!hasActiveProject}
        onClick={() => void navigate("/training")}
      >
        <Settings className="h-4 w-4 mr-1" />
        Open Config
      </Button>
      <Button
        size="sm"
        variant="outline"
        disabled={!hasActiveProject}
        onClick={() => void navigate("/compare")}
      >
        <BarChart2 className="h-4 w-4 mr-1" />
        Compare Runs
      </Button>
    </div>
  );
}
