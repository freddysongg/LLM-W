import * as React from "react";
import { cn } from "@/lib/utils";

export interface KVRow {
  readonly key: string;
  readonly value: React.ReactNode;
}

export interface KVListProps {
  readonly rows: readonly KVRow[];
  readonly className?: string;
  readonly dense?: boolean;
}

export function KVList({ rows, className, dense = false }: KVListProps): React.JSX.Element {
  return (
    <dl
      className={cn(
        "grid grid-cols-[auto_1fr] gap-x-4 text-[13px]",
        dense ? "gap-y-1" : "gap-y-2",
        className,
      )}
    >
      {rows.map(({ key, value }) => (
        <React.Fragment key={key}>
          <dt className="font-mono text-[11px] uppercase tracking-[0.08em] text-ink-3">{key}</dt>
          <dd className="font-mono text-ink-1">{value}</dd>
        </React.Fragment>
      ))}
    </dl>
  );
}
