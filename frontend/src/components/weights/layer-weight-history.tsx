import * as React from "react";

import { ChartBox } from "@/components/shared/chart-box";
import { useWeightSnapshotsForLayer } from "@/hooks/useWeightSnapshots";
import type { ChartSeries } from "@/components/shared/chart-box";

const NORM_SERIES_COLOR = "oklch(0.65 0.15 200)";
const MEAN_SERIES_COLOR = "oklch(0.65 0.15 140)";

interface LayerWeightHistoryProps {
  readonly projectId: string;
  readonly runId: string;
  readonly layerName: string;
}

export function LayerWeightHistory({
  projectId,
  runId,
  layerName,
}: LayerWeightHistoryProps): React.JSX.Element {
  const { data } = useWeightSnapshotsForLayer({ projectId, runId, layerName });

  if (data === undefined || data.points.length === 0) {
    return (
      <div className="font-mono text-[11px] text-ink-3">
        No weight snapshots yet for {layerName}.
      </div>
    );
  }

  const normSeries: ReadonlyArray<ChartSeries> = [
    {
      key: "norm",
      label: "norm",
      color: NORM_SERIES_COLOR,
      data: data.points.map((point) => ({ x: point.step, y: point.norm })),
    },
  ];
  const meanSeries: ReadonlyArray<ChartSeries> = [
    {
      key: "mean",
      label: "mean",
      color: MEAN_SERIES_COLOR,
      data: data.points.map((point) => ({ x: point.step, y: point.mean })),
    },
  ];

  return (
    <div className="space-y-3">
      <div className="font-mono text-[10px] uppercase tracking-wider text-ink-3">{layerName}</div>
      <ChartBox title="norm over checkpoints" series={normSeries} />
      <ChartBox title="mean over checkpoints" series={meanSeries} />
    </div>
  );
}
