import * as React from "react";

interface ActivationComparisonPanelProps {
  readonly runIds: ReadonlyArray<string>;
}

export function ActivationComparisonPanel({
  runIds,
}: ActivationComparisonPanelProps): React.JSX.Element {
  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Activation snapshots are captured at the project level via the Weights &amp; Architecture
        explorer. Capture snapshots before and after training runs to compare layer-level statistics
        (mean, std, min, max) across checkpoints.
      </p>
      <div className="rounded-md border p-4 text-sm text-muted-foreground">
        <p className="font-medium text-foreground mb-1">No activation snapshots available</p>
        <p>
          To compare activations for the selected runs, use the Architecture tab to capture
          activation snapshots, then return here to view cross-run layer statistics.
        </p>
        <ul className="mt-2 list-disc list-inside text-xs space-y-1">
          {runIds.map((runId) => (
            <li key={runId} className="font-mono">
              {runId.slice(0, 8)}&hellip;
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
