import * as React from "react";
import { Card } from "@/components/ui/card";
import type { FlowColumn, FlowNode } from "@/types/flow";

const COLUMN_WIDTH = 220;
const COLUMN_GAP = 48;
const NODE_HEIGHT = 32;
const NODE_GAP = 4;
const COLUMN_HEADER_HEIGHT = 56;
const COLUMN_PADDING = 12;

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

interface FlowVisualizationProps {
  readonly columns: ReadonlyArray<FlowColumn>;
  readonly onSelectNode: (fullPath: string) => void;
}

export function FlowVisualization({
  columns,
  onSelectNode,
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

  // Compute x positions for each column
  const columnPositions: number[] = [];
  let cursor = 0;
  for (const col of columns) {
    columnPositions.push(cursor);
    const isExpanded = expandedKeys.has(col.key);
    // Expanded repeated columns: each individual block gets a column
    const colCount = col.isRepeated && isExpanded ? col.repeatCount : 1;
    cursor += colCount * (COLUMN_WIDTH + COLUMN_GAP);
  }

  const totalWidth = cursor - COLUMN_GAP + 24; // trailing padding
  const maxHeight = Math.max(...columns.map((col) => columnHeight(col.nodes.length)), 200);
  const svgHeight = maxHeight;
  const centerY = svgHeight / 2;

  return (
    <div
      className="overflow-x-auto overflow-y-hidden"
      style={{ cursor: "grab" }}
      onMouseDown={(e) => {
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
      }}
    >
      <div
        style={{
          position: "relative",
          width: totalWidth,
          height: svgHeight + 24,
          minHeight: 260,
        }}
      >
        {/* SVG connector lines */}
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

        {/* Column cards */}
        {columns.map((col, idx) => {
          const isExpanded = expandedKeys.has(col.key);
          const baseX = columnPositions[idx]!;
          const height = columnHeight(col.nodes.length);

          if (col.isRepeated && isExpanded) {
            // Render N individual columns (all showing the same representative structure)
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
