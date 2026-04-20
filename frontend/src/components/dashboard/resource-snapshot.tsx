import * as React from "react";
import type { SystemHealthResponse } from "@/types/health";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";

interface ResourceSnapshotProps {
  readonly health: SystemHealthResponse;
}

interface MeterRowProps {
  readonly label: string;
  readonly percent: number;
  readonly detail: string;
}

function MeterRow({ label, percent, detail }: MeterRowProps): React.JSX.Element {
  const clampedPercent = Math.max(0, Math.min(100, percent));
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between">
        <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-ink-3">{label}</span>
        <span className="font-mono text-[12px] text-ink-1">{detail}</span>
      </div>
      <Progress value={clampedPercent} />
    </div>
  );
}

function usagePercent({ used, total }: { readonly used: number; readonly total: number }): number {
  if (total <= 0) return 0;
  return (used / total) * 100;
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

  const ramPercent = usagePercent({ used: ramUsedMb, total: ramTotalMb });
  const hasGpu =
    gpuAvailable && gpuMemoryUsedMb !== null && gpuMemoryTotalMb !== null && gpuMemoryTotalMb > 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle>System</CardTitle>
        <Badge variant="running">healthy</Badge>
      </CardHeader>
      <CardContent className="flex flex-col gap-3.5">
        {hasGpu ? (
          <>
            <MeterRow
              label={`GPU · ${gpuName ?? torchDevice}`}
              percent={usagePercent({ used: gpuMemoryUsedMb, total: gpuMemoryTotalMb })}
              detail={`${(gpuMemoryUsedMb / 1024).toFixed(1)} / ${(gpuMemoryTotalMb / 1024).toFixed(1)} GB`}
            />
            <MeterRow
              label="VRAM"
              percent={usagePercent({ used: gpuMemoryUsedMb, total: gpuMemoryTotalMb })}
              detail={`${((gpuMemoryUsedMb / gpuMemoryTotalMb) * 100).toFixed(0)}%`}
            />
          </>
        ) : (
          <div className="font-mono text-[11px] text-ink-3">
            Device: <span className="text-ink-1">{torchDevice}</span>
          </div>
        )}
        <MeterRow
          label="RAM"
          percent={ramPercent}
          detail={`${(ramUsedMb / 1024).toFixed(1)} / ${(ramTotalMb / 1024).toFixed(1)} GB`}
        />
      </CardContent>
    </Card>
  );
}
