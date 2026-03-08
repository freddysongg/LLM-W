import * as React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";

interface SystemResources {
  readonly gpuMemoryUsedMb: number;
  readonly gpuUtilizationPct: number;
  readonly cpuPct: number;
  readonly ramUsedMb: number;
}

interface SystemResourceMonitorProps {
  readonly resources: SystemResources | null;
}

function mbToGb(mb: number): string {
  return `${(mb / 1024).toFixed(1)} GB`;
}

export function SystemResourceMonitor({
  resources,
}: SystemResourceMonitorProps): React.JSX.Element {
  if (!resources) {
    return (
      <div className="text-sm text-muted-foreground py-4 text-center">
        Waiting for system metrics…
      </div>
    );
  }

  const { gpuMemoryUsedMb, gpuUtilizationPct, cpuPct, ramUsedMb } = resources;

  return (
    <div className="grid grid-cols-2 gap-3">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-xs text-muted-foreground font-normal">
            GPU Utilization
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-1">
          <Progress value={gpuUtilizationPct} className="h-2" />
          <div className="text-sm font-medium">{Math.round(gpuUtilizationPct)}%</div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-xs text-muted-foreground font-normal">GPU Memory</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-sm font-medium">{mbToGb(gpuMemoryUsedMb)}</div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-xs text-muted-foreground font-normal">CPU</CardTitle>
        </CardHeader>
        <CardContent className="space-y-1">
          <Progress value={cpuPct} className="h-2" />
          <div className="text-sm font-medium">{Math.round(cpuPct)}%</div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-xs text-muted-foreground font-normal">RAM</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-sm font-medium">{mbToGb(ramUsedMb)}</div>
        </CardContent>
      </Card>
    </div>
  );
}
