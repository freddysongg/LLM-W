import * as React from "react";

interface EffectiveShapeDiagramProps {
  readonly rank: number;
  readonly hiddenDim: number;
}

export function EffectiveShapeDiagram({
  rank,
  hiddenDim,
}: EffectiveShapeDiagramProps): React.JSX.Element {
  const safeRank = Math.max(1, rank);
  const rankThickness = 16 + safeRank * 0.6;
  const dotX = 270 + safeRank * 0.6;
  const matrixAX = 285 + safeRank * 0.6;
  const matrixALabelX = 365 + safeRank * 0.6;

  return (
    <svg
      viewBox="0 0 480 220"
      role="img"
      aria-label="LoRA effective shape"
      className="block w-full"
    >
      <rect
        x={30}
        y={30}
        width={160}
        height={160}
        fill="var(--surface-3)"
        stroke="var(--hairline-strong)"
      />
      <text
        x={110}
        y={120}
        fill="var(--ink-2)"
        fontSize={14}
        textAnchor="middle"
        fontFamily="var(--font-mono)"
      >
        W (frozen)
      </text>
      <text
        x={110}
        y={210}
        fill="var(--ink-3)"
        fontSize={10}
        textAnchor="middle"
        fontFamily="var(--font-mono)"
      >
        {hiddenDim} × {hiddenDim}
      </text>

      <text x={210} y={118} fill="var(--ink-2)" fontSize={22} textAnchor="middle">
        +
      </text>

      <rect
        x={230}
        y={30}
        width={rankThickness}
        height={160}
        fill="oklch(0.82 0.13 310)"
        opacity={0.75}
      />
      <text
        x={230 + rankThickness / 2}
        y={118}
        fill="white"
        fontSize={11}
        textAnchor="middle"
        fontFamily="var(--font-mono)"
      >
        B
      </text>
      <text
        x={230 + rankThickness / 2}
        y={210}
        fill="var(--ink-3)"
        fontSize={10}
        textAnchor="middle"
        fontFamily="var(--font-mono)"
      >
        {hiddenDim} × {safeRank}
      </text>

      <text x={dotX} y={118} fill="var(--ink-2)" fontSize={16} textAnchor="middle">
        ·
      </text>

      <rect
        x={matrixAX}
        y={108 - safeRank * 0.3}
        width={160}
        height={16 + safeRank * 0.6}
        fill="oklch(0.80 0.14 260)"
        opacity={0.75}
      />
      <text
        x={matrixALabelX}
        y={118}
        fill="white"
        fontSize={11}
        textAnchor="middle"
        fontFamily="var(--font-mono)"
      >
        A
      </text>
      <text
        x={matrixALabelX}
        y={210}
        fill="var(--ink-3)"
        fontSize={10}
        textAnchor="middle"
        fontFamily="var(--font-mono)"
      >
        {safeRank} × {hiddenDim}
      </text>
    </svg>
  );
}
