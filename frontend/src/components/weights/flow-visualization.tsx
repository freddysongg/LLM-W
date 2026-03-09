import * as React from "react";
import { Card } from "@/components/ui/card";
import type { FlowColumn, FlowMode, FlowNode, TokenRow } from "@/types/flow";
import type { ActivationSnapshotResponse, TierOneStats } from "@/types/model";

const COLUMN_WIDTH = 220;
const COLUMN_GAP = 48;
const ROW_GAP = 80;
const NODE_HEIGHT = 32;
const GROUP_HEADER_HEIGHT = 24;
const NODE_GAP = 4;
const COLUMN_HEADER_HEIGHT = 56;
const COLUMN_PADDING = 12;
// CANVAS_PADDING equals COLUMN_GAP so row-wrap arrows have room in the gutter
const CANVAS_PADDING = COLUMN_GAP;
const ACTIVATION_CELL_HEIGHT = 26;
const ACTIVATION_CELL_GAP = 2;
const MAX_DISPLAY_TOKENS = 64;

// ── Pure helpers ──────────────────────────────────────────────────────────────

function formatParamCount(params: number): string {
  if (params >= 1e9) return `${(params / 1e9).toFixed(2)}B`;
  if (params >= 1e6) return `${(params / 1e6).toFixed(2)}M`;
  if (params >= 1e3) return `${(params / 1e3).toFixed(1)}K`;
  return String(params);
}

function nodeHeight(node: FlowNode): number {
  return node.isGroupHeader ? GROUP_HEADER_HEIGHT : NODE_HEIGHT;
}

function columnHeight(nodes: ReadonlyArray<FlowNode>): number {
  const nodesHeight = nodes.reduce((acc, n) => acc + nodeHeight(n) + NODE_GAP, 0);
  return COLUMN_HEADER_HEIGHT + COLUMN_PADDING + nodesHeight + COLUMN_PADDING;
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
    .filter((n) => !n.isGroupHeader)
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
    if (node.isGroupHeader) continue;
    const stats = layerStats.get(node.fullPath);
    if (stats) return stats;
  }
  return null;
}

function buildFlatColumns(
  columns: ReadonlyArray<FlowColumn>,
  expandedKeys: ReadonlySet<string>,
): ReadonlyArray<FlowColumn> {
  return columns.flatMap((col) => {
    if (col.isRepeated && expandedKeys.has(col.key)) {
      return Array.from({ length: col.repeatCount }, (_, i) => ({
        ...col,
        key: `${col.key}-${i}`,
        label: `${col.label} [${i}]`,
        isRepeated: false,
        repeatCount: 1,
      }));
    }
    return [col];
  });
}

interface ColPosition {
  readonly x: number;
  readonly y: number;
}

interface GridLayout {
  readonly colPositions: ReadonlyArray<ColPosition>;
  readonly colHeights: ReadonlyArray<number>;
  readonly canvasWidth: number;
  readonly canvasHeight: number;
}

function computeGridLayout({
  flatColumns,
  colsPerRow,
}: {
  flatColumns: ReadonlyArray<FlowColumn>;
  colsPerRow: number;
}): GridLayout {
  const colHeights = flatColumns.map((col) => columnHeight(col.nodes));
  const rowCount = Math.ceil(flatColumns.length / colsPerRow);

  const rowHeights: number[] = [];
  for (let r = 0; r < rowCount; r++) {
    const slice = colHeights.slice(r * colsPerRow, (r + 1) * colsPerRow);
    rowHeights.push(Math.max(...slice, 200));
  }

  const rowTops: number[] = [0];
  for (let r = 1; r < rowCount; r++) {
    rowTops.push(rowTops[r - 1]! + rowHeights[r - 1]! + ROW_GAP);
  }

  const colPositions: ColPosition[] = flatColumns.map((_, idx) => ({
    x: (idx % colsPerRow) * (COLUMN_WIDTH + COLUMN_GAP),
    y: rowTops[Math.floor(idx / colsPerRow)]!,
  }));

  const canvasWidth =
    Math.min(flatColumns.length, colsPerRow) * (COLUMN_WIDTH + COLUMN_GAP) - COLUMN_GAP;
  const canvasHeight = rowTops[rowCount - 1]! + rowHeights[rowCount - 1]!;
  return { colPositions, colHeights, canvasWidth, canvasHeight };
}

function buildSameRowArrowPath(x1: number, y1: number, x2: number, y2: number): string {
  const cx = (x1 + x2) / 2;
  return `M ${x1} ${y1} C ${cx} ${y1}, ${cx} ${y2}, ${x2} ${y2}`;
}

function buildWrapArrowPath({
  x1,
  y1,
  x2,
  y2,
  rightG,
  leftG,
  midY,
}: {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  rightG: number;
  leftG: number;
  midY: number;
}): string {
  // U-turn through the gutter: right → down → left → down → right
  const r = 8;
  return [
    `M ${x1} ${y1}`,
    `L ${rightG - r} ${y1}`,
    `Q ${rightG} ${y1} ${rightG} ${y1 + r}`,
    `L ${rightG} ${midY - r}`,
    `Q ${rightG} ${midY} ${rightG - r} ${midY}`,
    `L ${leftG + r} ${midY}`,
    `Q ${leftG} ${midY} ${leftG} ${midY + r}`,
    `L ${leftG} ${y2 - r}`,
    `Q ${leftG} ${y2} ${leftG + r} ${y2}`,
    `L ${x2} ${y2}`,
  ].join(" ");
}

// ── Pan hook ──────────────────────────────────────────────────────────────────

interface PanState {
  readonly panOffset: { readonly x: number; readonly y: number };
  readonly handleMouseDown: (e: React.MouseEvent<HTMLDivElement>) => void;
}

function usePanCanvas(): PanState {
  const [panOffset, setPanOffset] = React.useState({ x: CANVAS_PADDING, y: CANVAS_PADDING });
  const isPanningRef = React.useRef(false);
  const lastMouseRef = React.useRef({ x: 0, y: 0 });

  const handleMouseDown = React.useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    isPanningRef.current = true;
    lastMouseRef.current = { x: e.clientX, y: e.clientY };
  }, []);

  React.useEffect(() => {
    const onMove = (e: MouseEvent): void => {
      if (!isPanningRef.current) return;
      const dx = e.clientX - lastMouseRef.current.x;
      const dy = e.clientY - lastMouseRef.current.y;
      lastMouseRef.current = { x: e.clientX, y: e.clientY };
      setPanOffset((prev) => ({ x: prev.x + dx, y: prev.y + dy }));
    };
    const onUp = (): void => {
      isPanningRef.current = false;
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, []);

  return { panOffset, handleMouseDown };
}

// ── Structural mode sub-components ───────────────────────────────────────────

interface FlowNodeRowProps {
  readonly node: FlowNode;
  readonly onSelect: (fullPath: string) => void;
}

function FlowNodeRow({ node, onSelect }: FlowNodeRowProps): React.JSX.Element {
  const indent = node.depth * 12;
  const height = nodeHeight(node);

  if (node.isGroupHeader) {
    return (
      <div
        className="flex items-center gap-1 text-xs text-muted-foreground/80 select-none shrink-0"
        style={{ height, paddingLeft: indent + 4 }}
        title={`${node.name} · ${node.type}`}
      >
        <span className="font-mono font-semibold truncate flex-1">{node.name}</span>
        <span className="shrink-0 text-muted-foreground/50 text-[10px]">{node.type}</span>
      </div>
    );
  }

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
        "flex items-center gap-2 pr-2 rounded cursor-pointer select-none text-xs shrink-0",
        "hover:bg-muted/60 transition-colors",
        isTrainable ? "border border-primary/30 bg-primary/5" : "",
        isFrozen ? "opacity-50" : "",
      ]
        .filter(Boolean)
        .join(" ")}
      style={{ height, paddingLeft: indent + 8 }}
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
  readonly y: number;
  readonly height: number;
}

function FlowColumnCard({
  column,
  isExpanded,
  onToggleExpand,
  onSelectNode,
  x,
  y,
  height,
}: FlowColumnCardProps): React.JSX.Element {
  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
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
        <div
          className="flex-1 overflow-hidden flex flex-col"
          style={{ padding: COLUMN_PADDING, gap: NODE_GAP }}
        >
          {column.nodes.map((node) => (
            <FlowNodeRow key={node.fullPath} node={node} onSelect={onSelectNode} />
          ))}
        </div>
      </Card>
    </div>
  );
}

interface ConnectorPathProps {
  readonly x1: number;
  readonly y1: number;
  readonly x2: number;
  readonly y2: number;
  readonly isWrap: boolean;
  readonly rightG: number;
  readonly leftG: number;
  readonly midY: number;
  readonly markerId: string;
  readonly strokeColor?: string;
  readonly strokeOpacity?: number;
  readonly strokeWidth?: number;
}

function ConnectorPath({
  x1,
  y1,
  x2,
  y2,
  isWrap,
  rightG,
  leftG,
  midY,
  markerId,
  strokeColor = "hsl(var(--muted-foreground))",
  strokeOpacity = 0.4,
  strokeWidth = 1.5,
}: ConnectorPathProps): React.JSX.Element {
  const d = isWrap
    ? buildWrapArrowPath({ x1, y1, x2, y2, rightG, leftG, midY })
    : buildSameRowArrowPath(x1, y1, x2, y2);
  return (
    <path
      d={d}
      fill="none"
      stroke={strokeColor}
      strokeOpacity={strokeOpacity}
      strokeWidth={strokeWidth}
      markerEnd={`url(#${markerId})`}
    />
  );
}

// ── Structural canvas ─────────────────────────────────────────────────────────

interface StructuralCanvasProps {
  readonly columns: ReadonlyArray<FlowColumn>;
  readonly expandedKeys: ReadonlySet<string>;
  readonly onToggleExpand: (key: string) => void;
  readonly onSelectNode: (fullPath: string) => void;
}

function StructuralCanvas({
  columns,
  expandedKeys,
  onToggleExpand,
  onSelectNode,
}: StructuralCanvasProps): React.JSX.Element {
  const containerRef = React.useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = React.useState(800);
  const { panOffset, handleMouseDown } = usePanCanvas();

  React.useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new ResizeObserver(([entry]) => {
      if (entry) setContainerWidth(entry.contentRect.width);
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const flatColumns = React.useMemo(
    () => buildFlatColumns(columns, expandedKeys),
    [columns, expandedKeys],
  );

  // Fit as many columns per row as possible given the container width
  const colsPerRow = Math.max(
    1,
    Math.floor((containerWidth - 2 * CANVAS_PADDING + COLUMN_GAP) / (COLUMN_WIDTH + COLUMN_GAP)),
  );

  const { colPositions, colHeights, canvasWidth, canvasHeight } = React.useMemo(
    () => computeGridLayout({ flatColumns, colsPerRow }),
    [flatColumns, colsPerRow],
  );

  // SVG viewport includes padding so row-wrap gutter arrows stay within bounds
  const svgWidth = canvasWidth + 2 * CANVAS_PADDING;
  const svgHeight = canvasHeight + 2 * CANVAS_PADDING;

  // Gutter x-coords in SVG space for row-wrap arrows
  const wrapRightG = CANVAS_PADDING + canvasWidth + COLUMN_GAP / 2;
  const wrapLeftG = CANVAS_PADDING - COLUMN_GAP / 2;

  return (
    <div
      ref={containerRef}
      className="relative overflow-hidden w-full h-full cursor-grab active:cursor-grabbing select-none"
      onMouseDown={handleMouseDown}
    >
      <div
        style={{
          position: "absolute",
          transform: `translate(${panOffset.x}px, ${panOffset.y}px)`,
          width: svgWidth,
          height: svgHeight,
        }}
      >
        <svg
          style={{ position: "absolute", top: 0, left: 0, pointerEvents: "none" }}
          width={svgWidth}
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
          {flatColumns.map((col, idx) => {
            if (idx === flatColumns.length - 1) return null;
            const pos = colPositions[idx]!;
            const nextPos = colPositions[idx + 1]!;
            const h = colHeights[idx]!;
            const nextH = colHeights[idx + 1]!;

            // Arrow exits from right-center of source, enters left-center of destination
            const x1 = CANVAS_PADDING + pos.x + COLUMN_WIDTH;
            const y1 = CANVAS_PADDING + pos.y + h / 2;
            const x2 = CANVAS_PADDING + nextPos.x;
            const y2 = CANVAS_PADDING + nextPos.y + nextH / 2;

            const rowIdx = Math.floor(idx / colsPerRow);
            const nextRowIdx = Math.floor((idx + 1) / colsPerRow);
            const isWrap = rowIdx !== nextRowIdx;
            const midY = (y1 + y2) / 2;

            return (
              <ConnectorPath
                key={`connector-${col.key}`}
                x1={x1}
                y1={y1}
                x2={x2}
                y2={y2}
                isWrap={isWrap}
                rightG={wrapRightG}
                leftG={wrapLeftG}
                midY={midY}
                markerId="arrowhead"
              />
            );
          })}
        </svg>

        {flatColumns.map((col, idx) => {
          const pos = colPositions[idx]!;
          const height = colHeights[idx]!;
          return (
            <FlowColumnCard
              key={col.key}
              column={col}
              isExpanded={expandedKeys.has(col.key)}
              onToggleExpand={() => onToggleExpand(col.key)}
              onSelectNode={onSelectNode}
              x={CANVAS_PADDING + pos.x}
              y={CANVAS_PADDING + pos.y}
              height={height}
            />
          );
        })}
      </div>
    </div>
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
  readonly y: number;
  readonly height: number;
  readonly tokenRows: ReadonlyArray<TokenRow>;
  readonly stats: TierOneStats | null;
  readonly normalizedIntensity: number | null;
}

function ActivationColumnCard({
  column,
  x,
  y,
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
        top: y,
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

// ── Activation canvas ─────────────────────────────────────────────────────────

interface ActivationCanvasProps {
  readonly columns: ReadonlyArray<FlowColumn>;
  readonly snapshot: ActivationSnapshotResponse;
  readonly sampleInput: string;
}

function ActivationCanvas({
  columns,
  snapshot,
  sampleInput,
}: ActivationCanvasProps): React.JSX.Element {
  const { panOffset, handleMouseDown } = usePanCanvas();

  const tokenRows = React.useMemo(() => tokenizeInput(sampleInput), [sampleInput]);
  const layerStats = React.useMemo(() => buildLayerStatsMap(snapshot), [snapshot]);

  const columnMeans = columns.map((col) => computeColumnMean(col, layerStats));
  const columnStats = columns.map((col) => computeColumnRepresentativeStats(col, layerStats));

  const validMeans = columnMeans.filter((m): m is number => m !== null);
  const globalMin = validMeans.length > 0 ? Math.min(...validMeans) : 0;
  const globalMax = validMeans.length > 0 ? Math.max(...validMeans) : 1;
  const range = globalMax - globalMin || 1;
  const normalizedMeans = columnMeans.map((m) => (m === null ? null : (m - globalMin) / range));

  const cardHeight = activationColumnHeight(Math.max(tokenRows.length, 1));
  const totalWidth = columns.length * (COLUMN_WIDTH + COLUMN_GAP) - COLUMN_GAP;
  const svgWidth = totalWidth + 2 * CANVAS_PADDING;
  const svgHeight = cardHeight + 2 * CANVAS_PADDING;
  const centerY = CANVAS_PADDING + cardHeight / 2;

  return (
    <div
      className="relative overflow-hidden w-full h-full cursor-grab active:cursor-grabbing select-none"
      onMouseDown={handleMouseDown}
    >
      <div
        style={{
          position: "absolute",
          transform: `translate(${panOffset.x}px, ${panOffset.y}px)`,
          width: svgWidth,
          height: svgHeight,
        }}
      >
        <svg
          style={{ position: "absolute", top: 0, left: 0, pointerEvents: "none" }}
          width={svgWidth}
          height={svgHeight}
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
            const x1 = CANVAS_PADDING + idx * (COLUMN_WIDTH + COLUMN_GAP) + COLUMN_WIDTH;
            const x2 = CANVAS_PADDING + (idx + 1) * (COLUMN_WIDTH + COLUMN_GAP);
            const intensity = normalizedMeans[idx] ?? 0;
            const t = Math.max(0, Math.min(1, intensity));
            const strokeWidth = 1.5 + 4.5 * t;
            const strokeOpacity = 0.2 + 0.7 * t;
            const hue = Math.round(210 + 57 * t);
            return (
              <ConnectorPath
                key={`act-connector-${col.key}`}
                x1={x1}
                y1={centerY}
                x2={x2}
                y2={centerY}
                isWrap={false}
                rightG={0}
                leftG={0}
                midY={0}
                markerId="arrowhead-activation"
                strokeColor={`hsl(${hue}, 60%, 50%)`}
                strokeOpacity={strokeOpacity}
                strokeWidth={strokeWidth}
              />
            );
          })}
        </svg>

        {columns.map((col, idx) => (
          <ActivationColumnCard
            key={col.key}
            column={col}
            x={CANVAS_PADDING + idx * (COLUMN_WIDTH + COLUMN_GAP)}
            y={CANVAS_PADDING}
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
      <ActivationCanvas columns={columns} snapshot={activationSnapshot} sampleInput={sampleInput} />
    );
  }

  return (
    <StructuralCanvas
      columns={columns}
      expandedKeys={expandedKeys}
      onToggleExpand={toggleExpand}
      onSelectNode={onSelectNode}
    />
  );
}
