import * as React from "react";
import type { ModelArchitectureResponse, LayerNode } from "@/types/model";

interface ArchitectureDiagramProps {
  readonly architecture: ModelArchitectureResponse;
}

interface DiagramGeometry {
  readonly layerCount: number;
  readonly embedDim: number | null;
  readonly vocabSize: number | null;
}

function findFirstLayerStack(node: LayerNode): LayerNode | null {
  const children = node.children ?? [];
  for (const child of children) {
    const grandChildren = child.children ?? [];
    if (grandChildren.length > 1) {
      const allSameType = grandChildren.every((g) => g.type === grandChildren[0].type);
      if (allSameType && grandChildren.length >= 2) {
        return child;
      }
    }
    const deeper = findFirstLayerStack(child);
    if (deeper) return deeper;
  }
  return null;
}

function findEmbeddingDim(node: LayerNode): number | null {
  if (node.type.toLowerCase().includes("embedding") && node.shape && node.shape.length >= 2) {
    return node.shape[1];
  }
  for (const child of node.children ?? []) {
    const match = findEmbeddingDim(child);
    if (match !== null) return match;
  }
  return null;
}

function findVocabSize(node: LayerNode): number | null {
  if (node.type.toLowerCase().includes("embedding") && node.shape && node.shape.length >= 2) {
    return node.shape[0];
  }
  for (const child of node.children ?? []) {
    const match = findVocabSize(child);
    if (match !== null) return match;
  }
  return null;
}

function computeGeometry({ tree }: { tree: LayerNode }): DiagramGeometry {
  const stack = findFirstLayerStack(tree);
  const layerCount = stack ? (stack.children ?? []).length : 0;
  return {
    layerCount,
    embedDim: findEmbeddingDim(tree),
    vocabSize: findVocabSize(tree),
  };
}

const MAX_BARS = 28;

export function ArchitectureDiagram({ architecture }: ArchitectureDiagramProps): React.JSX.Element {
  const { layerCount, embedDim, vocabSize } = React.useMemo(
    () => computeGeometry({ tree: architecture.tree }),
    [architecture],
  );

  const barCount = Math.max(1, Math.min(MAX_BARS, layerCount || MAX_BARS));
  const barWidth = 12;
  const barGap = 4;
  const startX = 20;
  const baseY = 60;
  const barMaxHeight = 140;

  const embedLabel = embedDim ? `input · embed(${embedDim.toLocaleString()})` : "input · embed";
  const stackLabel = `${layerCount || "N"} × (attn + mlp + norm)`;
  const headLabel = vocabSize
    ? `lm_head · softmax → ${vocabSize.toLocaleString()}`
    : "lm_head · softmax";

  return (
    <svg
      viewBox="0 0 480 260"
      role="img"
      aria-label="Architecture diagram"
      className="block w-full"
    >
      <defs>
        <linearGradient id="architecture-layer-gradient" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="oklch(0.88 0.14 150)" />
          <stop offset="1" stopColor="oklch(0.82 0.13 310)" />
        </linearGradient>
      </defs>
      {Array.from({ length: barCount }, (_, i) => {
        const stagger = (i % 3) * 4;
        const height = barMaxHeight - (i % 3) * 8;
        return (
          <rect
            key={i}
            x={startX + i * (barWidth + barGap)}
            y={baseY + stagger}
            width={barWidth}
            height={height}
            rx={2}
            fill="url(#architecture-layer-gradient)"
            opacity={0.6 + (i / barCount) * 0.4}
          />
        );
      })}
      <text x={startX} y={50} fontFamily="var(--font-mono)" fontSize={10} fill="var(--ink-3)">
        {embedLabel}
      </text>
      <text x={startX} y={220} fontFamily="var(--font-mono)" fontSize={10} fill="var(--ink-3)">
        {stackLabel}
      </text>
      <text x={startX} y={240} fontFamily="var(--font-mono)" fontSize={10} fill="var(--ink-3)">
        {headLabel}
      </text>
    </svg>
  );
}
