import * as React from "react";
import type { SystemHealthResponse } from "@/types/health";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";

interface ResourceSnapshotProps {
  readonly health: SystemHealthResponse;
}

function usagePct(used: number, total: number): number {
  if (total === 0) return 0;
  return Math.round((used / total) * 100);
}

interface ResourceRowProps {
  readonly label: string;
  readonly pct: number;
  readonly detail: string;
}

function ResourceRow({ label, pct, detail }: ResourceRowProps): React.JSX.Element {
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-sm">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-medium">{detail}</span>
      </div>
      <Progress value={pct} />
    </div>
  );
}

export function ResourceSnapshot({ health }: ResourceSnapshotProps): React.JSX.Element {
  const {
    ramUsedMb,
    ramTotalMb,
    gpuAvailable,
    gpuMemoryUsedMb,
    gpuMemoryTotalMb,
    gpuName,
    torchDevice,
  } = health;

  const ramPct = usagePct(ramUsedMb, ramTotalMb);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Resources</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <ResourceRow
          label="RAM"
          pct={ramPct}
          detail={`${Math.round(ramUsedMb / 1024)} / ${Math.round(ramTotalMb / 1024)} GB`}
        />
        {gpuAvailable && gpuMemoryUsedMb !== null && gpuMemoryTotalMb !== null ? (
          <ResourceRow
            label={gpuName ?? "GPU"}
            pct={usagePct(gpuMemoryUsedMb, gpuMemoryTotalMb)}
            detail={`${Math.round(gpuMemoryUsedMb / 1024)} / ${Math.round(gpuMemoryTotalMb / 1024)} GB`}
          />
        ) : (
          <div className="text-xs text-muted-foreground">
            Device: <span className="font-medium">{torchDevice}</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
