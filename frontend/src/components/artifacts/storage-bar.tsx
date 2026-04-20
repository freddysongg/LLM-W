import * as React from "react";

export interface StorageBarSegment {
  readonly label: string;
  readonly bytes: number;
  readonly color: string;
}

export interface StorageBarProps {
  readonly segments: ReadonlyArray<StorageBarSegment>;
  readonly totalBytes: number;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

export function StorageBar({ segments, totalBytes }: StorageBarProps): React.JSX.Element {
  const safeTotal = Math.max(totalBytes, 1);
  const usedBytes = segments.reduce<number>((sum, entry) => sum + entry.bytes, 0);
  const filledSegments = segments.filter((entry) => entry.bytes > 0);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between font-mono text-[11px] text-ink-3">
        <span>{formatBytes(usedBytes)} used</span>
        <span>of {formatBytes(safeTotal)}</span>
      </div>
      <div
        className="flex h-[10px] w-full overflow-hidden rounded-[6px]"
        style={{ background: "var(--surface-3)" }}
        aria-hidden="true"
      >
        {filledSegments.map((segment) => {
          const widthPercent = (segment.bytes / safeTotal) * 100;
          return (
            <div
              key={segment.label}
              className="h-full"
              style={{ width: `${widthPercent}%`, background: segment.color }}
            />
          );
        })}
      </div>
      <ul className="flex flex-col gap-1.5">
        {segments.map((segment) => (
          <li
            key={segment.label}
            className="flex items-center justify-between font-mono text-[11px] text-ink-2"
          >
            <span className="flex items-center gap-2">
              <span
                aria-hidden="true"
                className="h-2 w-2 rounded-[2px]"
                style={{ background: segment.color }}
              />
              {segment.label}
            </span>
            <span className="text-ink-1">{formatBytes(segment.bytes)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
