import * as React from "react";

export interface VramSegment {
  readonly label: string;
  readonly gb: number;
  readonly color: string;
}

interface VramBudgetBarProps {
  readonly segments: ReadonlyArray<VramSegment>;
  readonly totalGb: number;
}

export function VramBudgetBar({ segments, totalGb }: VramBudgetBarProps): React.JSX.Element {
  const usedGb = segments.reduce((sum, segment) => sum + segment.gb, 0);
  const freeGb = Math.max(0, totalGb - usedGb);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex h-7 overflow-hidden rounded-md border border-hairline">
        {segments.map((segment) => (
          <div
            key={segment.label}
            title={`${segment.label}: ${segment.gb.toFixed(1)} GB`}
            style={{ flex: segment.gb, backgroundColor: segment.color }}
          />
        ))}
        {freeGb > 0 ? (
          <div
            title={`Free: ${freeGb.toFixed(1)} GB`}
            style={{ flex: freeGb }}
            className="bg-surface-3"
          />
        ) : null}
      </div>

      <dl className="flex flex-col gap-1.5">
        {segments.map((segment) => (
          <div key={segment.label} className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span
                aria-hidden="true"
                className="inline-block size-2.5 rounded-[3px]"
                style={{ backgroundColor: segment.color }}
              />
              <dt className="font-mono text-[11px] text-ink-2">{segment.label}</dt>
            </div>
            <dd className="font-mono text-[11px] text-ink-1">{segment.gb.toFixed(1)} GB</dd>
          </div>
        ))}
        <div className="flex items-center justify-between border-t border-dashed border-hairline pt-2">
          <dt className="font-mono text-[11px] text-ink-3">Used / total</dt>
          <dd className="font-mono text-[12px] text-ink-1">
            {usedGb.toFixed(1)} / {totalGb.toFixed(0)} GB
          </dd>
        </div>
      </dl>
    </div>
  );
}
