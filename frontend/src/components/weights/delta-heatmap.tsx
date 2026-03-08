import * as React from "react";
import type { WeightDelta } from "@/types/model";

interface DeltaHeatmapProps {
  readonly deltas: ReadonlyArray<WeightDelta>;
}

function interpolateColor(ratio: number): string {
  // blue (low) → red (high)
  const r = Math.round(ratio * 220);
  const b = Math.round((1 - ratio) * 220);
  return `rgb(${r}, 30, ${b})`;
}

export function DeltaHeatmap({ deltas }: DeltaHeatmapProps): React.JSX.Element {
  if (deltas.length === 0) {
    return (
      <div className="py-8 text-center text-sm text-muted-foreground">
        No delta data. Capture two activation snapshots to compare.
      </div>
    );
  }

  const maxMag = Math.max(...deltas.map((d) => d.deltaMagnitude), 1e-9);

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <span>Low Δ</span>
        <div className="flex h-3 w-24 rounded overflow-hidden">
          {Array.from({ length: 24 }, (_, i) => (
            <div key={i} className="flex-1" style={{ backgroundColor: interpolateColor(i / 23) }} />
          ))}
        </div>
        <span>High Δ</span>
      </div>

      <div className="flex flex-wrap gap-1">
        {deltas.map(({ layerName, deltaMagnitude }) => {
          const ratio = deltaMagnitude / maxMag;
          return (
            <div
              key={layerName}
              title={`${layerName}: Δ=${deltaMagnitude.toFixed(5)}`}
              className="h-8 flex items-center justify-center rounded cursor-default text-white text-xs font-mono"
              style={{
                backgroundColor: interpolateColor(ratio),
                minWidth: "6rem",
                maxWidth: "10rem",
                padding: "0 6px",
              }}
            >
              <span className="truncate">{layerName.split(".").slice(-1)[0]}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
