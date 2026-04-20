import * as React from "react";

interface ArchEndcapProps {
  readonly label: string;
  readonly shape: string;
}

export function ArchEndcap({ label, shape }: ArchEndcapProps): React.JSX.Element {
  return (
    <div className="flex min-w-[72px] shrink-0 flex-col justify-center gap-0.5 px-1 py-1">
      <span className="font-mono text-[10px] font-semibold uppercase tracking-[0.06em] text-ink-2">
        {label}
      </span>
      <span className="font-mono text-[9.5px] text-ink-4">{shape}</span>
    </div>
  );
}
