import * as React from "react";
import { Card } from "@/components/ui/card";
import type { FlowColumn, FlowMode, FlowNode, TokenRow } from "@/types/flow";
import type { ActivationSnapshotResponse, TierOneStats } from "@/types/model";

const COLUMN_WIDTH = 220;
const COLUMN_GAP = 48;
const NODE_HEIGHT = 32;
const NODE_GAP = 4;
const COLUMN_HEADER_HEIGHT = 56;
const COLUMN_PADDING = 12;
const ACTIVATION_CELL_HEIGHT = 26;
const ACTIVATION_CELL_GAP = 2;
const MAX_DISPLAY_TOKENS = 64;

function formatParamCount(params: number): string {
  if (params >= 1e9) return `${(params / 1e9).toFixed(2)}B`;
  if (params >= 1e6) return `${(params / 1e6).toFixed(2)}M`;
  if (params >= 1e3) return `${(params / 1e3).toFixed(1)}K`;
  return String(params);
}

function columnHeight(nodeCount: number): number {
  return (
    COLUMN_HEADER_HEIGHT + COLUMN_PADDING + nodeCount * (NODE_HEIGHT + NODE_GAP) + COLUMN_PADDING
  );
}

function activationColumnHeight(tokenCount: number): number {
  return (
    COLUMN_HEADER_HEIGHT +
    COLUMN_PADDING +
    tokenCount * (ACTIVATION_CELL_HEIGHT + ACTIVATION_CELL_GAP) +
    COLUMN_PADDING
  );
}

function interpolateActivationColor(normalizedValue: number): string {
  const t = Math.max(0, Math.min(1, normalizedValue));
  const hue = Math.round(210 + 57 * t);
  const sat = Math.round(40 + 20 * t);
  const lit = Math.round(35 + 20 * t);
  const alpha = (0.2 + 0.65 * t).toFixed(2);
  return `hsla(${hue}, ${sat}%, ${lit}%, ${alpha})`;
}

function tokenizeInput(sampleInput: string): ReadonlyArray<TokenRow> {
  return sampleInput
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, MAX_DISPLAY_TOKENS)
    .map((tokenString, position) => ({ tokenString, position }));
}

function buildLayerStatsMap(snapshot: ActivationSnapshotResponse): Map<string, TierOneStats> {
  return new Map(snapshot.layers.map((l) => [l.layer_name, l.tier1]));
}

function computeColumnMean(
  column: FlowColumn,
  layerStats: Map<string, TierOneStats>,
): number | null {
  const means = column.nodes
    .map((n) => layerStats.get(n.fullPath)?.mean)
    .filter((v): v is number => v !== undefined);
  if (means.length === 0) return null;
  return means.reduce((a, b) => a + b, 0) / means.length;
}

function computeColumnRepresentativeStats(
  column: FlowColumn,
  layerStats: Map<string, TierOneStats>,
): TierOneStats | null {
  for (const node of column.nodes) {
    const stats = layerStats.get(node.fullPath);
    if (stats) return stats;
  }
  return null;
}

// ── Structural mode sub-components ───────────────────────────────────────────

interface FlowNodeRowProps {
  readonly node: FlowNode;
  readonly onSelect: (fullPath: string) => void;
}

function FlowNodeRow({ node, onSelect }: FlowNodeRowProps): React.JSX.Element {
  const isFrozen = node.trainable === false;
  const isTrainable = node.trainable === true;

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => onSelect(node.fullPath)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") onSelect(node.fullPath);
      }}
      title={[
        node.name,
        node.type,
        node.params !== null ? formatParamCount(node.params) + " params" : null,
        node.shape ? `[${node.shape.join(", ")}]` : null,
        node.trainable === true ? "trainable" : node.trainable === false ? "frozen" : null,
      ]
        .filter(Boolean)
        .join(" · ")}
      className={[
        "flex items-center gap-2 px-2 rounded cursor-pointer select-none text-xs",
        "hover:bg-muted/60 transition-colors",
        isTrainable ? "border border-primary/30 bg-primary/5" : "",
        isFrozen ? "opacity-50" : "",
      ]
        .filter(Boolean)
        .join(" ")}
      style={{ height: NODE_HEIGHT }}
    >
      <span className="font-mono truncate flex-1">{node.name}</span>
      <span className="text-muted-foreground shrink-0">{node.type}</span>
      {node.params !== null && node.params > 0 && (
        <span className="text-muted-foreground/70 shrink-0">{formatParamCount(node.params)}</span>
      )}
    </div>
  );
}

interface FlowColumnCardProps {
  readonly column: FlowColumn;
  readonly isExpanded: boolean;
  readonly onToggleExpand: () => void;
  readonly onSelectNode: (fullPath: string) => void;
  readonly x: number;
  readonly height: number;
}

function FlowColumnCard({
  column,
  isExpanded,
  onToggleExpand,
  onSelectNode,
  x,
  height,
}: FlowColumnCardProps): React.JSX.Element {
  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: 0,
        width: COLUMN_WIDTH,
        height,
      }}
    >
      <Card className="h-full flex flex-col overflow-hidden">
        <div className="px-3 py-2 border-b shrink-0" style={{ height: COLUMN_HEADER_HEIGHT }}>
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm font-medium truncate flex-1">{column.label}</span>
            {column.isRepeated && (
              <button
                onClick={onToggleExpand}
                className="shrink-0 text-xs font-semibold px-1.5 py-0.5 rounded bg-muted text-muted-foreground hover:bg-muted/80 transition-colors"
              >
                {column.repeatCount}×
              </button>
            )}
          </div>
          {column.totalParams > 0 && (
            <div className="text-xs text-muted-foreground mt-0.5">
              {formatParamCount(column.totalParams)}
            </div>
          )}
          {column.isRepeated && (
            <div className="text-xs text-muted-foreground/60 mt-0.5">
              {isExpanded ? "click × to collapse" : "click × to expand"}
            </div>
          )}
        </div>
        <div className="flex-1 overflow-hidden p-2 space-y-1" style={{ gap: NODE_GAP }}>
          {column.nodes.map((node) => (
            <FlowNodeRow key={node.fullPath} node={node} onSelect={onSelectNode} />
          ))}
        </div>
      </Card>
    </div>
  );
}

interface ConnectorLineProps {
  readonly x1: number;
  readonly x2: number;
  readonly centerY: number;
}

function ConnectorLine({ x1, x2, centerY }: ConnectorLineProps): React.JSX.Element {
  const midX = (x1 + x2) / 2;
  const d = `M ${x1} ${centerY} C ${midX} ${centerY}, ${midX} ${centerY}, ${x2} ${centerY}`;
  return (
    <path
      d={d}
      fill="none"
      stroke="hsl(var(--muted-foreground))"
      strokeOpacity={0.4}
      strokeWidth={1.5}
      markerEnd="url(#arrowhead)"
    />
  );
}

// ── Activation mode sub-components ───────────────────────────────────────────

interface ActivationCellProps {
  readonly token: TokenRow;
  readonly columnLabel: string;
  readonly stats: TierOneStats | null;
  readonly normalizedIntensity: number | null;
}

function ActivationCell({
  token,
  columnLabel,
  stats,
  normalizedIntensity,
}: ActivationCellProps): React.JSX.Element {
  const bgColor =
    stats !== null && normalizedIntensity !== null
      ? interpolateActivationColor(normalizedIntensity)
      : "transparent";

  const title =
    stats !== null
      ? [
          `token: "${token.tokenString}"`,
          `layer: ${columnLabel}`,
          `mean: ${stats.mean.toFixed(4)}`,
          `std: ${stats.std.toFixed(4)}`,
          `min: ${stats.min.toFixed(4)}`,
          `max: ${stats.max.toFixed(4)}`,
        ].join("\n")
      : `token: "${token.tokenString}" — no activation data for ${columnLabel}`;

  return (
    <div
      title={title}
      style={{
        height: ACTIVATION_CELL_HEIGHT,
        marginBottom: ACTIVATION_CELL_GAP,
        backgroundColor: bgColor,
        borderRadius: 3,
      }}
      className="flex items-center px-2"
    >
      <span className="font-mono text-xs truncate text-foreground/80">{token.tokenString}</span>
    </div>
  );
}

interface ActivationColumnCardProps {
  readonly column: FlowColumn;
  readonly x: number;
  readonly height: number;
  readonly tokenRows: ReadonlyArray<TokenRow>;
  readonly stats: TierOneStats | null;
  readonly normalizedIntensity: number | null;
}

function ActivationColumnCard({
  column,
  x,
  height,
  tokenRows,
  stats,
  normalizedIntensity,
}: ActivationColumnCardProps): React.JSX.Element {
  const headerBorderColor =
    stats !== null && normalizedIntensity !== null
      ? interpolateActivationColor(Math.min(1, normalizedIntensity * 1.2))
      : undefined;

  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: 0,
        width: COLUMN_WIDTH,
        height,
      }}
    >
      <Card className="h-full flex flex-col overflow-hidden">
        <div
          className="px-3 py-2 border-b shrink-0"
          style={{
            height: COLUMN_HEADER_HEIGHT,
            borderBottomColor: headerBorderColor,
          }}
        >
          <span className="font-mono text-sm font-medium truncate block">{column.label}</span>
          {stats !== null ? (
            <div className="text-xs text-muted-foreground mt-0.5">mean {stats.mean.toFixed(3)}</div>
          ) : (
            <div className="text-xs text-muted-foreground/50 mt-0.5">no data</div>
          )}
        </div>
        <div className="flex-1 overflow-hidden p-2">
          {tokenRows.map((token) => (
            <ActivationCell
              key={token.position}
              token={token}
              columnLabel={column.label}
              stats={stats}
              normalizedIntensity={normalizedIntensity}
            />
          ))}
        </div>
      </Card>
    </div>
  );
}

interface ActivationConnectorLineProps {
  readonly x1: number;
  readonly x2: number;
  readonly centerY: number;
  readonly normalizedIntensity: number;
}

function ActivationConnectorLine({
  x1,
  x2,
  centerY,
  normalizedIntensity,
}: ActivationConnectorLineProps): React.JSX.Element {
  const t = Math.max(0, Math.min(1, normalizedIntensity));
  const strokeWidth = 1.5 + 4.5 * t;
  const strokeOpacity = 0.2 + 0.7 * t;
  const hue = Math.round(210 + 57 * t);
  const midX = (x1 + x2) / 2;
  const d = `M ${x1} ${centerY} C ${midX} ${centerY}, ${midX} ${centerY}, ${x2} ${centerY}`;
  return (
    <path
      d={d}
      fill="none"
      stroke={`hsl(${hue}, 60%, 50%)`}
      strokeOpacity={strokeOpacity}
      strokeWidth={strokeWidth}
      markerEnd="url(#arrowhead-activation)"
    />
  );
}

interface ActivationOverlayProps {
  readonly columns: ReadonlyArray<FlowColumn>;
  readonly snapshot: ActivationSnapshotResponse;
  readonly sampleInput: string;
  readonly onScrollDrag: (e: React.MouseEvent<HTMLDivElement>) => void;
}

function ActivationOverlay({
  columns,
  snapshot,
  sampleInput,
  onScrollDrag,
}: ActivationOverlayProps): React.JSX.Element {
  const tokenRows = tokenizeInput(sampleInput);
  const layerStats = buildLayerStatsMap(snapshot);

  const columnMeans = columns.map((col) => computeColumnMean(col, layerStats));
  const columnStats = columns.map((col) => computeColumnRepresentativeStats(col, layerStats));

  const validMeans = columnMeans.filter((m): m is number => m !== null);
  const globalMin = validMeans.length > 0 ? Math.min(...validMeans) : 0;
  const globalMax = validMeans.length > 0 ? Math.max(...validMeans) : 1;
  const range = globalMax - globalMin || 1;

  const normalizedMeans = columnMeans.map((m) => (m === null ? null : (m - globalMin) / range));

  // Flat column layout for activation mode (no expand/collapse)
  let cursor = 0;
  const columnPositions = columns.map(() => {
    const x = cursor;
    cursor += COLUMN_WIDTH + COLUMN_GAP;
    return x;
  });

  const totalWidth = cursor - COLUMN_GAP + 24;
  const cardHeight = activationColumnHeight(Math.max(tokenRows.length, 1));
  const centerY = cardHeight / 2;

  return (
    <div
      className="overflow-x-auto overflow-y-hidden"
      style={{ cursor: "grab" }}
      onMouseDown={onScrollDrag}
    >
      <div
        style={{
          position: "relative",
          width: totalWidth,
          height: cardHeight + 24,
          minHeight: 200,
        }}
      >
        <svg
          style={{ position: "absolute", top: 0, left: 0, pointerEvents: "none" }}
          width={totalWidth}
          height={cardHeight}
        >
          <defs>
            <marker
              id="arrowhead-activation"
              markerWidth="6"
              markerHeight="4"
              refX="6"
              refY="2"
              orient="auto"
            >
              <polygon points="0 0, 6 2, 0 4" fill="hsl(240, 50%, 50%)" fillOpacity={0.6} />
            </marker>
          </defs>
          {columns.map((col, idx) => {
            if (idx === columns.length - 1) return null;
            const x1 = columnPositions[idx]! + COLUMN_WIDTH;
            const x2 = columnPositions[idx + 1]!;
            const intensity = normalizedMeans[idx] ?? 0;
            return (
              <ActivationConnectorLine
                key={`act-connector-${col.key}`}
                x1={x1}
                x2={x2}
                centerY={centerY}
                normalizedIntensity={intensity}
              />
            );
          })}
        </svg>

        {columns.map((col, idx) => (
          <ActivationColumnCard
            key={col.key}
            column={col}
            x={columnPositions[idx]!}
            height={cardHeight}
            tokenRows={tokenRows}
            stats={columnStats[idx] ?? null}
            normalizedIntensity={normalizedMeans[idx] ?? null}
          />
        ))}
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

interface FlowVisualizationProps {
  readonly columns: ReadonlyArray<FlowColumn>;
  readonly onSelectNode: (fullPath: string) => void;
  readonly mode: FlowMode;
  readonly activationSnapshot: ActivationSnapshotResponse | null;
  readonly onCaptureRequest: () => void;
  readonly isCapturing: boolean;
  readonly sampleInput: string;
}

export function FlowVisualization({
  columns,
  onSelectNode,
  mode,
  activationSnapshot,
  onCaptureRequest,
  isCapturing,
  sampleInput,
}: FlowVisualizationProps): React.JSX.Element {
  const [expandedKeys, setExpandedKeys] = React.useState<ReadonlySet<string>>(new Set());

  const toggleExpand = (key: string): void => {
    setExpandedKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const handleScrollDrag = React.useCallback((e: React.MouseEvent<HTMLDivElement>): void => {
    const el = e.currentTarget;
    const startX = e.pageX + el.scrollLeft;
    const onMove = (ev: MouseEvent): void => {
      el.scrollLeft = startX - ev.pageX;
    };
    const onUp = (): void => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }, []);

  if (columns.length === 0) {
    return (
      <div className="py-12 text-center text-sm text-muted-foreground">
        No architecture data to visualize.
      </div>
    );
  }

  if (mode === "activation") {
    if (!activationSnapshot) {
      return (
        <div className="py-12 text-center space-y-3">
          <p className="text-sm text-muted-foreground">
            Enter a sample prompt above and capture activations to see the activation overlay.
          </p>
          <button
            onClick={onCaptureRequest}
            disabled={isCapturing || !sampleInput.trim()}
            className="px-3 py-1.5 text-xs font-medium rounded bg-primary text-primary-foreground disabled:opacity-50 hover:bg-primary/90 transition-colors"
          >
            {isCapturing ? "Capturing…" : "Capture Activations"}
          </button>
        </div>
      );
    }

    return (
      <ActivationOverlay
        columns={columns}
        snapshot={activationSnapshot}
        sampleInput={sampleInput}
        onScrollDrag={handleScrollDrag}
      />
    );
  }

  // ── Structural mode ─────────────────────────────────────────────────────────

  const columnPositions: number[] = [];
  let cursor = 0;
  for (const col of columns) {
    columnPositions.push(cursor);
    const isExpanded = expandedKeys.has(col.key);
    const colCount = col.isRepeated && isExpanded ? col.repeatCount : 1;
    cursor += colCount * (COLUMN_WIDTH + COLUMN_GAP);
  }

  const totalWidth = cursor - COLUMN_GAP + 24;
  const maxHeight = Math.max(...columns.map((col) => columnHeight(col.nodes.length)), 200);
  const svgHeight = maxHeight;
  const centerY = svgHeight / 2;

  return (
    <div
      className="overflow-x-auto overflow-y-hidden"
      style={{ cursor: "grab" }}
      onMouseDown={handleScrollDrag}
    >
      <div
        style={{
          position: "relative",
          width: totalWidth,
          height: svgHeight + 24,
          minHeight: 260,
        }}
      >
        <svg
          style={{ position: "absolute", top: 0, left: 0, pointerEvents: "none" }}
          width={totalWidth}
          height={svgHeight}
        >
          <defs>
            <marker id="arrowhead" markerWidth="6" markerHeight="4" refX="6" refY="2" orient="auto">
              <polygon
                points="0 0, 6 2, 0 4"
                fill="hsl(var(--muted-foreground))"
                fillOpacity={0.4}
              />
            </marker>
          </defs>
          {columns.map((col, idx) => {
            if (idx === columns.length - 1) return null;
            const isExpanded = expandedKeys.has(col.key);
            const colCount = col.isRepeated && isExpanded ? col.repeatCount : 1;
            const x1 =
              columnPositions[idx]! + colCount * COLUMN_WIDTH + (colCount - 1) * COLUMN_GAP;
            const x2 = columnPositions[idx + 1]!;
            return <ConnectorLine key={`connector-${col.key}`} x1={x1} x2={x2} centerY={centerY} />;
          })}
        </svg>

        {columns.map((col, idx) => {
          const isExpanded = expandedKeys.has(col.key);
          const baseX = columnPositions[idx]!;
          const height = columnHeight(col.nodes.length);

          if (col.isRepeated && isExpanded) {
            return Array.from({ length: col.repeatCount }, (_, i) => (
              <FlowColumnCard
                key={`${col.key}-expanded-${i}`}
                column={{
                  ...col,
                  label: `${col.label} [${i}]`,
                  isRepeated: false,
                  repeatCount: 1,
                }}
                isExpanded={false}
                onToggleExpand={() => toggleExpand(col.key)}
                onSelectNode={onSelectNode}
                x={baseX + i * (COLUMN_WIDTH + COLUMN_GAP)}
                height={height}
              />
            ));
          }

          return (
            <FlowColumnCard
              key={col.key}
              column={col}
              isExpanded={isExpanded}
              onToggleExpand={() => toggleExpand(col.key)}
              onSelectNode={onSelectNode}
              x={baseX}
              height={height}
            />
          );
        })}
      </div>
    </div>
  );
}
