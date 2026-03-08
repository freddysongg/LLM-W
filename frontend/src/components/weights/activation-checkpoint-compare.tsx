import * as React from "react";
import type { ActivationSnapshotResponse } from "@/types/model";

interface ActivationCheckpointCompareProps {
  readonly snapshotA: ActivationSnapshotResponse;
  readonly snapshotB: ActivationSnapshotResponse;
}

function formatStat(value: number): string {
  return value.toFixed(4);
}

export function ActivationCheckpointCompare({
  snapshotA,
  snapshotB,
}: ActivationCheckpointCompareProps): React.JSX.Element {
  const layerNamesA = new Set(snapshotA.layers.map((l) => l.layer_name));
  const sharedLayers = snapshotB.layers.filter((l) => layerNamesA.has(l.layer_name));

  if (sharedLayers.length === 0) {
    return (
      <div className="py-4 text-sm text-muted-foreground">
        No matching layers between the two snapshots.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-3 text-xs font-medium text-muted-foreground border-b pb-1">
        <span>Layer</span>
        <span className="text-center">
          Snapshot A — {new Date(snapshotA.created_at).toLocaleTimeString()}
        </span>
        <span className="text-center">
          Snapshot B — {new Date(snapshotB.created_at).toLocaleTimeString()}
        </span>
      </div>

      {sharedLayers.map((layerB) => {
        const layerA = snapshotA.layers.find((l) => l.layer_name === layerB.layer_name);
        if (!layerA) return null;

        return (
          <div key={layerB.layer_name} className="grid grid-cols-3 text-xs border-b pb-2 gap-2">
            <span className="font-mono truncate" title={layerB.layer_name}>
              {layerB.layer_name}
            </span>
            <div className="text-center space-y-0.5">
              <p className="font-mono">μ {formatStat(layerA.tier1.mean)}</p>
              <p className="text-muted-foreground font-mono">σ {formatStat(layerA.tier1.std)}</p>
            </div>
            <div className="text-center space-y-0.5">
              <p className="font-mono">μ {formatStat(layerB.tier1.mean)}</p>
              <p className="text-muted-foreground font-mono">σ {formatStat(layerB.tier1.std)}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
