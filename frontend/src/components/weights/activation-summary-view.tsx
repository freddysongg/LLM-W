import * as React from "react";
import type { ActivationSnapshotResponse, ActivationLayerSnapshot } from "@/types/model";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface ActivationSummaryViewProps {
  readonly snapshot: ActivationSnapshotResponse;
}

interface HistogramDataPoint {
  readonly bin: number;
  readonly count: number;
}

function buildHistogramData(bins: ReadonlyArray<number>): ReadonlyArray<HistogramDataPoint> {
  return bins.map((count, idx) => ({ bin: idx, count }));
}

function LayerSummaryCard({ layer }: { layer: ActivationLayerSnapshot }): React.JSX.Element {
  const { tier1, layer_name, shape } = layer;
  const histogramData = buildHistogramData(tier1.histogram_bins);

  return (
    <Card>
      <CardHeader className="pb-1">
        <CardTitle className="text-xs font-mono truncate" title={layer_name}>
          {layer_name}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <div className="grid grid-cols-4 gap-2 text-xs">
          <div>
            <p className="text-muted-foreground">mean</p>
            <p className="font-mono font-medium">{tier1.mean.toFixed(4)}</p>
          </div>
          <div>
            <p className="text-muted-foreground">std</p>
            <p className="font-mono font-medium">{tier1.std.toFixed(4)}</p>
          </div>
          <div>
            <p className="text-muted-foreground">min</p>
            <p className="font-mono font-medium">{tier1.min.toFixed(4)}</p>
          </div>
          <div>
            <p className="text-muted-foreground">max</p>
            <p className="font-mono font-medium">{tier1.max.toFixed(4)}</p>
          </div>
        </div>

        {shape.length > 0 && (
          <p className="text-xs text-muted-foreground font-mono">shape: [{shape.join(", ")}]</p>
        )}

        {histogramData.length > 0 && (
          <div className="h-16">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={histogramData as HistogramDataPoint[]}
                margin={{ top: 0, right: 0, left: 0, bottom: 0 }}
              >
                <XAxis dataKey="bin" hide />
                <YAxis hide />
                <Tooltip
                  formatter={(value: number) => [value.toFixed(2), "count"]}
                  labelFormatter={(label) => `bin ${label}`}
                />
                <Bar dataKey="count" fill="hsl(var(--primary))" radius={[1, 1, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function ActivationSummaryView({ snapshot }: ActivationSummaryViewProps): React.JSX.Element {
  if (snapshot.layers.length === 0) {
    return (
      <div className="py-8 text-center text-sm text-muted-foreground">
        No layer data in this snapshot.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">
        Snapshot captured {new Date(snapshot.created_at).toLocaleString()} —{" "}
        {snapshot.layers.length} layers
      </p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {snapshot.layers.map((layer) => (
          <LayerSummaryCard key={layer.layer_name} layer={layer} />
        ))}
      </div>
    </div>
  );
}
