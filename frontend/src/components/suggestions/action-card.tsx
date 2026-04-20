import * as React from "react";
import { Sparkle } from "lucide-react";
import { CodeBlock } from "@/components/shared/code-block";
import { Button } from "@/components/ui/button";

export interface ActionCardProps {
  readonly optLabel: string;
  readonly impact: number;
  readonly label: string;
  readonly patch?: string;
  readonly isApplying: boolean;
  readonly canAct: boolean;
  readonly onPreview: () => void;
  readonly onApply: () => void;
}

function impactColorFor(impact: number): string {
  if (impact > 0.7) return "var(--success)";
  if (impact > 0.5) return "var(--info)";
  return "var(--ink-3)";
}

export function ActionCard({
  optLabel,
  impact,
  label,
  patch,
  isApplying,
  canAct,
  onPreview,
  onApply,
}: ActionCardProps): React.JSX.Element {
  const clampedImpact = Math.max(0, Math.min(1, impact));
  const impactPercent = Math.round(clampedImpact * 100);
  const impactColor = impactColorFor(clampedImpact);

  return (
    <div
      className="grid items-stretch gap-3.5 rounded-[10px] border border-hairline bg-surface-2 p-3.5 transition-[background-color,border-color] duration-[var(--dur-1)] hover:border-hairline-strong hover:bg-surface"
      style={{ gridTemplateColumns: "36px 1fr auto" }}
    >
      <div className="flex flex-col items-center gap-1.5">
        <span
          className="inline-flex items-center gap-1 rounded-[6px] border px-1.5 py-0.5 font-mono text-[10px] font-bold uppercase tracking-[0.04em] text-[color:var(--iris-4)]"
          style={{
            background:
              "linear-gradient(135deg, color-mix(in oklch, var(--iris-1) 55%, white), color-mix(in oklch, var(--iris-2) 35%, white))",
            borderColor: "color-mix(in oklch, var(--iris-3) 35%, var(--hairline))",
          }}
        >
          <Sparkle className="h-2.5 w-2.5 text-[color:var(--iris-4)]" aria-hidden="true" />
          <span>{optLabel}</span>
        </span>
        <div
          className="relative flex w-[3px] flex-1 items-end overflow-hidden rounded-[2px]"
          style={{
            background: "color-mix(in oklch, var(--hairline) 40%, transparent)",
            minHeight: 30,
          }}
          title={`${impactPercent}% confidence`}
        >
          <div
            className="w-full rounded-[2px] transition-[height] duration-[var(--dur-2)] ease-[cubic-bezier(0.22,1,0.36,1)]"
            style={{ height: `${impactPercent}%`, background: impactColor }}
          />
        </div>
      </div>
      <div className="min-w-0">
        <div className="text-[13px] font-medium text-ink-1">{label}</div>
        {patch ? <CodeBlock code={patch} copyable={false} className="mt-1.5" /> : null}
      </div>
      <div className="flex items-center gap-1.5 self-center">
        <Button variant="outline" size="sm" onClick={onPreview} disabled={isApplying}>
          Preview
        </Button>
        <Button variant="primary" size="sm" onClick={onApply} disabled={!canAct || isApplying}>
          {isApplying ? "Applying…" : "Apply"}
        </Button>
      </div>
    </div>
  );
}
