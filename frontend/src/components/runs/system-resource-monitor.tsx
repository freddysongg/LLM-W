import * as React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Counter } from "@/components/shared/counter";

interface SystemResources {
  readonly gpuMemoryUsedMb: number;
  readonly gpuUtilizationPct: number;
  readonly cpuPct: number;
  readonly ramUsedMb: number;
}

interface SystemResourceMonitorProps {
  readonly resources: SystemResources | null;
}

interface TileProps {
  readonly label: string;
  readonly value: number;
  readonly decimals: number;
  readonly suffix: string;
  readonly progressPercent: number;
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
  const clampedPercent = Math.max(0, Math.min(100, progressPercent));
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle>{label}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <div className="font-mono text-[28px] font-semibold leading-none tracking-[-0.02em] text-ink-1">
          <Counter value={value} decimals={decimals} suffix={suffix} />
        </div>
        <Progress value={clampedPercent} />
        {sub ? <div className="font-mono text-[10.5px] text-ink-3">{sub}</div> : null}
      </CardContent>
    </Card>
  );
}

const VRAM_TOTAL_GB_FALLBACK = 40;
const RAM_TOTAL_GB_FALLBACK = 64;

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

  const { gpuMemoryUsedMb, gpuUtilizationPct, cpuPct, ramUsedMb } = resources;
  const vramGb = gpuMemoryUsedMb / 1024;
  const ramGb = ramUsedMb / 1024;

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
      <ResourceTile
        label="GPU utilization"
        value={gpuUtilizationPct}
        decimals={0}
        suffix="%"
        progressPercent={gpuUtilizationPct}
        sub="live from trainer"
      />
      <ResourceTile
        label="VRAM"
        value={vramGb}
        decimals={1}
        suffix=" GB"
        progressPercent={(vramGb / VRAM_TOTAL_GB_FALLBACK) * 100}
        sub={`of ${VRAM_TOTAL_GB_FALLBACK.toFixed(1)} GB`}
      />
      <ResourceTile
        label="CPU / RAM"
        value={cpuPct}
        decimals={0}
        suffix="%"
        progressPercent={cpuPct}
        sub={`${ramGb.toFixed(1)} / ${RAM_TOTAL_GB_FALLBACK.toFixed(1)} GB RAM`}
      />
    </div>
  );
}
