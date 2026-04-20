import * as React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { RangePills } from "@/components/shared/range-pills";
import { cn } from "@/lib/utils";

type LayerInspectorView = "heatmap" | "histogram" | "grad";

interface LayerSummary {
  readonly index: number;
  readonly attnStrength: number;
  readonly mlpStrength: number;
}

interface LayerInspectorProps {
  readonly layers: ReadonlyArray<LayerSummary>;
  readonly selectedLayerIndex: number;
  readonly onSelectLayer: (layerIndex: number) => void;
  readonly selectedLayerLabel: string;
  readonly stats: {
    readonly mean: number;
    readonly std: number;
    readonly max: number;
  };
}

const VIEW_OPTIONS: ReadonlyArray<{ readonly value: LayerInspectorView; readonly label: string }> =
  [
    { value: "heatmap", label: "heatmap" },
    { value: "histogram", label: "histogram" },
    { value: "grad", label: "grad" },
  ];

const HEATMAP_CELLS = 16;
const HEATMAP_SEED = 1337;

function pseudoRandom(seed: number): number {
  const x = Math.sin(seed) * 10000;
  return x - Math.floor(x);
}

function buildHeatmapMatrix(): ReadonlyArray<ReadonlyArray<number>> {
  const matrix: number[][] = [];
  for (let y = 0; y < HEATMAP_CELLS; y += 1) {
    const row: number[] = [];
    for (let x = 0; x < HEATMAP_CELLS; x += 1) {
      row.push(pseudoRandom(HEATMAP_SEED + y * HEATMAP_CELLS + x));
    }
    matrix.push(row);
  }
  return matrix;
}

function HeatmapView(): React.JSX.Element {
  const matrix = React.useMemo(() => buildHeatmapMatrix(), []);
  const cellWidth = 26;
  const cellHeight = 14;
  return (
    <svg viewBox="0 0 480 280" role="img" aria-label="Weight heatmap" className="block w-full">
      {matrix.map((row, y) =>
        row.map((value, x) => {
          const mix = Math.round(20 + value * 75);
          return (
            <rect
              key={`${y}-${x}`}
              x={20 + x * (cellWidth + 2)}
              y={10 + y * (cellHeight + 2)}
              width={cellWidth}
              height={cellHeight}
              rx={1}
              fill={`color-mix(in oklch, var(--iris-3) ${mix}%, var(--surface))`}
              opacity={0.5 + value * 0.5}
            />
          );
        }),
      )}
    </svg>
  );
}

function HistogramView(): React.JSX.Element {
  const binCount = 32;
  return (
    <svg viewBox="0 0 480 220" role="img" aria-label="Weight histogram" className="block w-full">
      {Array.from({ length: binCount }, (_, i) => {
        const value = Math.exp(-Math.pow((i - binCount / 2) / 6, 2)) * 150;
        return (
          <rect
            key={i}
            x={20 + i * 14}
            y={180 - value}
            width={10}
            height={value}
            fill="var(--iris-3)"
            opacity={0.55 + i / 60}
          />
        );
      })}
      <line x1={20} x2={468} y1={180} y2={180} stroke="var(--hairline)" strokeDasharray="2 3" />
      <text x={20} y={200} fontFamily="var(--font-mono)" fontSize={10} fill="var(--ink-3)">
        -0.5
      </text>
      <text
        x={240}
        y={200}
        fontFamily="var(--font-mono)"
        fontSize={10}
        fill="var(--ink-3)"
        textAnchor="middle"
      >
        0
      </text>
      <text
        x={468}
        y={200}
        fontFamily="var(--font-mono)"
        fontSize={10}
        fill="var(--ink-3)"
        textAnchor="end"
      >
        +0.5
      </text>
    </svg>
  );
}

function GradView(): React.JSX.Element {
  const pointCount = 50;
  return (
    <svg
      viewBox="0 0 480 220"
      role="img"
      aria-label="Gradient L2 over time"
      className="block w-full"
    >
      {Array.from({ length: pointCount }, (_, i) => {
        const height = 60 + Math.sin(i / 3) * 40 + pseudoRandom(i * 9.3) * 20;
        return (
          <rect
            key={i}
            x={10 + i * 9.3}
            y={180 - height}
            width={7}
            height={height}
            fill="oklch(0.82 0.13 310)"
            opacity={0.6}
          />
        );
      })}
      <line x1={10} x2={470} y1={180} y2={180} stroke="var(--hairline)" strokeDasharray="2 3" />
      <text x={10} y={200} fontFamily="var(--font-mono)" fontSize={10} fill="var(--ink-3)">
        step 0
      </text>
      <text
        x={470}
        y={200}
        fontFamily="var(--font-mono)"
        fontSize={10}
        fill="var(--ink-3)"
        textAnchor="end"
      >
        step 2840
      </text>
    </svg>
  );
}

interface LayerSidebarProps {
  readonly layers: ReadonlyArray<LayerSummary>;
  readonly selectedLayerIndex: number;
  readonly onSelectLayer: (layerIndex: number) => void;
}

function LayerSidebar({
  layers,
  selectedLayerIndex,
  onSelectLayer,
}: LayerSidebarProps): React.JSX.Element {
  return (
    <Card className="flex flex-col">
      <CardHeader>
        <CardTitle>Layers</CardTitle>
        <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-ink-3">
          {layers.length}
        </span>
      </CardHeader>
      <div className="max-h-[560px] overflow-y-auto">
        {layers.map((layer) => {
          const isActive = layer.index === selectedLayerIndex;
          return (
            <button
              key={layer.index}
              type="button"
              aria-pressed={isActive}
              onClick={() => onSelectLayer(layer.index)}
              className={cn(
                "flex w-full items-center gap-2.5 border-l-2 border-transparent bg-transparent px-3 py-2",
                "text-left font-mono text-[11px] text-ink-2",
                "transition-[background-color,border-color,color] duration-[var(--dur-1)]",
                "hover:bg-surface-2",
                isActive && "border-[color:var(--iris-3)] bg-surface-2 text-ink-1",
              )}
            >
              <span className="w-8 shrink-0 text-ink-3">L{layer.index}</span>
              <span className="flex flex-1 flex-col gap-[3px]">
                <span
                  className="h-1 rounded-[2px]"
                  style={{
                    width: `${layer.attnStrength * 100}%`,
                    backgroundColor: "oklch(0.82 0.13 310)",
                  }}
                />
                <span
                  className="h-1 rounded-[2px]"
                  style={{
                    width: `${layer.mlpStrength * 100}%`,
                    backgroundColor: "oklch(0.80 0.14 260)",
                  }}
                />
              </span>
            </button>
          );
        })}
      </div>
    </Card>
  );
}

export function LayerInspector({
  layers,
  selectedLayerIndex,
  onSelectLayer,
  selectedLayerLabel,
  stats,
}: LayerInspectorProps): React.JSX.Element {
  const [view, setView] = React.useState<LayerInspectorView>("heatmap");
  const viewCaption =
    view === "heatmap" ? "colormap iris" : view === "histogram" ? "64 bins" : "grad L2 over time";

  return (
    <div className="grid gap-4 lg:grid-cols-[260px_1fr]">
      <LayerSidebar
        layers={layers}
        selectedLayerIndex={selectedLayerIndex}
        onSelectLayer={onSelectLayer}
      />
      <div className="flex flex-col gap-3">
        <Card>
          <CardHeader>
            <div className="space-y-0.5">
              <CardTitle>
                Layer {selectedLayerIndex} · {selectedLayerLabel}
              </CardTitle>
              <p className="font-mono text-[11px] text-ink-3">{viewCaption}</p>
            </div>
            <RangePills options={VIEW_OPTIONS} value={view} onChange={setView} />
          </CardHeader>
          <CardContent>
            {view === "heatmap" ? <HeatmapView /> : null}
            {view === "histogram" ? <HistogramView /> : null}
            {view === "grad" ? <GradView /> : null}
          </CardContent>
        </Card>
        <div className="grid grid-cols-3 gap-2">
          <div className="flex flex-col gap-1 rounded-md border border-hairline bg-surface-2 p-3">
            <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-ink-3">μ</span>
            <span className="font-mono text-[16px] font-semibold text-ink-1">
              {stats.mean.toFixed(4)}
            </span>
          </div>
          <div className="flex flex-col gap-1 rounded-md border border-hairline bg-surface-2 p-3">
            <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-ink-3">σ</span>
            <span className="font-mono text-[16px] font-semibold text-ink-1">
              {stats.std.toFixed(4)}
            </span>
          </div>
          <div className="flex flex-col gap-1 rounded-md border border-hairline bg-surface-2 p-3">
            <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-ink-3">
              max
            </span>
            <span className="font-mono text-[16px] font-semibold text-ink-1">
              {stats.max.toFixed(4)}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
