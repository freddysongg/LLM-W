import * as React from "react";

export function ArchWire(): React.JSX.Element {
  return (
    <svg
      viewBox="0 0 28 40"
      preserveAspectRatio="none"
      aria-hidden="true"
      className="h-8 w-[22px] shrink-0 self-center text-ink-4"
    >
      <path
        d="M 0 20 L 24 20 M 20 16 L 24 20 L 20 24"
        stroke="currentColor"
        strokeWidth={1}
        fill="none"
      />
    </svg>
  );
}
