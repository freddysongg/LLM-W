import * as React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Counter } from "@/components/shared/counter";

interface SystemResources {
  readonly gpuMemoryUsedMb: number;
  readonly vramTotalMb: number | null;
  readonly cpuPct: number;
  readonly ramUsedMb: number;
  readonly ramTotalMb: number;
}

interface SystemResourceMonitorProps {
  readonly resources: SystemResources | null;
}

interface TileProps {
  readonly label: string;
  readonly value: number;
  readonly decimals: number;
  readonly suffix: string;
  readonly progressPercent: number | null;
  readonly sub?: string;
}

function ResourceTile({
  label,
  value,
  decimals,
  suffix,
  progressPercent,
  sub,
}: TileProps): React.JSX.Element {
  const clampedPercent =
    progressPercent !== null ? Math.max(0, Math.min(100, progressPercent)) : null;
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle>{label}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <div className="font-mono text-[28px] font-semibold leading-none tracking-[-0.02em] text-ink-1">
          <Counter value={value} decimals={decimals} suffix={suffix} />
        </div>
        {clampedPercent !== null ? <Progress value={clampedPercent} /> : null}
        {sub ? <div className="font-mono text-[10.5px] text-ink-3">{sub}</div> : null}
      </CardContent>
    </Card>
  );
}

export function SystemResourceMonitor({
  resources,
}: SystemResourceMonitorProps): React.JSX.Element {
  if (!resources) {
    return (
      <Card>
        <CardContent className="py-4 text-center font-mono text-[11px] text-ink-3">
          Waiting for system metrics…
        </CardContent>
      </Card>
    );
  }

  const { gpuMemoryUsedMb, vramTotalMb, cpuPct, ramUsedMb, ramTotalMb } = resources;
  const vramGb = gpuMemoryUsedMb / 1024;
  const ramGb = ramUsedMb / 1024;
  const ramTotalGb = ramTotalMb / 1024;
  const hasVramTotal = vramTotalMb !== null && vramTotalMb > 0;
  const vramTotalGb = hasVramTotal ? vramTotalMb / 1024 : null;
  const vramPct = hasVramTotal ? (gpuMemoryUsedMb / vramTotalMb) * 100 : null;
  const ramPct = ramTotalMb > 0 ? (ramUsedMb / ramTotalMb) * 100 : 0;

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
      <ResourceTile
        label="VRAM"
        value={vramGb}
        decimals={1}
        suffix=" GB"
        progressPercent={vramPct}
        sub={
          vramTotalGb !== null
            ? `of ${vramTotalGb.toFixed(1)} GB`
            : "total unavailable on this platform"
        }
      />
      <ResourceTile
        label="RAM"
        value={ramGb}
        decimals={1}
        suffix=" GB"
        progressPercent={ramPct}
        sub={`of ${ramTotalGb.toFixed(1)} GB`}
      />
      <ResourceTile label="CPU" value={cpuPct} decimals={0} suffix="%" progressPercent={cpuPct} />
    </div>
  );
}
