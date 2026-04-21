import * as React from "react";

import { useRunModelProfile } from "@/hooks/useRunModelProfile";
import { useWeightSnapshotsAll } from "@/hooks/useWeightSnapshots";
import type { RunLayerProfile } from "@/types/run-model-profile";
import type { LayerWeightStats } from "@/types/weight-snapshot";

const DEAD_LAYER_REL_NORM_THRESHOLD = 0.001;

interface LayerTreeProps {
  readonly projectId: string;
  readonly runId: string;
  readonly selectedLayer: string | null;
  readonly onSelectLayer: (layerName: string) => void;
}

export function LayerTree({
  projectId,
  runId,
  selectedLayer,
  onSelectLayer,
}: LayerTreeProps): React.JSX.Element {
  const { data: profile, isLoading } = useRunModelProfile({ projectId, runId });
  const { data: snapshots } = useWeightSnapshotsAll({ projectId, runId });

  const deadLayers = React.useMemo<ReadonlySet<string>>(() => {
    if (profile === undefined || snapshots === undefined) return new Set<string>();
    const dead = new Set<string>();
    for (const layer of profile.layers) {
      if (!layer.trainable) continue;
      const series = snapshots.snapshotsByLayer[layer.name] ?? [];
      if (series.length < 2) continue;
      if (isLayerNotLearning(series)) dead.add(layer.name);
    }
    return dead;
  }, [profile, snapshots]);

  if (isLoading) {
    return <div className="font-mono text-[11px] text-ink-3">Loading profile…</div>;
  }
  if (profile === undefined) {
    return (
      <div className="font-mono text-[11px] text-ink-3">
        No model profile recorded for this run yet.
      </div>
    );
  }

  const trainablePct =
    profile.totalParams > 0
      ? ((profile.trainableParams / profile.totalParams) * 100).toFixed(1)
      : "0.0";

  return (
    <div className="flex flex-col gap-1 font-mono text-[11px]">
      <div className="mb-2 text-[10px] uppercase tracking-wider text-ink-3">
        {profile.totalParams.toLocaleString()} params · {profile.trainableParams.toLocaleString()}{" "}
        trainable ({trainablePct}%)
      </div>
      {profile.layers.map((layer) => (
        <LayerRow
          key={layer.name}
          layer={layer}
          isSelected={selectedLayer === layer.name}
          isDead={deadLayers.has(layer.name)}
          onClick={() => onSelectLayer(layer.name)}
        />
      ))}
    </div>
  );
}

interface LayerRowProps {
  readonly layer: RunLayerProfile;
  readonly isSelected: boolean;
  readonly isDead: boolean;
  readonly onClick: () => void;
}

function LayerRow({ layer, isSelected, isDead, onClick }: LayerRowProps): React.JSX.Element {
  const rowClass = isSelected ? "border-ink-1 bg-muted/40" : "border-transparent hover:bg-muted/20";
  const trainableClass = layer.trainable ? "" : "text-ink-3";
  return (
    <button
      type="button"
      onClick={onClick}
      className={`grid grid-cols-[1fr_90px_80px_90px] gap-2 rounded border px-2 py-1.5 text-left ${rowClass} ${trainableClass}`}
    >
      <span className="truncate">{layer.name}</span>
      <span className="text-right tabular-nums">{layer.paramCount.toLocaleString()}</span>
      <span className="text-center">{layer.trainable ? "trainable" : "frozen"}</span>
      <span className="text-right">
        {isDead ? <span className="text-amber-600">not learning</span> : null}
      </span>
    </button>
  );
}

function isLayerNotLearning(series: ReadonlyArray<LayerWeightStats>): boolean {
  for (let i = 1; i < series.length; i++) {
    const prev = series[i - 1].norm;
    const curr = series[i].norm;
    if (prev === 0) continue;
    if (Math.abs((curr - prev) / prev) >= DEAD_LAYER_REL_NORM_THRESHOLD) return false;
  }
  return true;
}
