import * as React from "react";
import { AlertTriangle } from "lucide-react";
import type { EvalCostWarningPayload } from "@/types/eval";

interface CostWarningBannerProps {
  readonly warning: EvalCostWarningPayload;
}

function formatUsd(amount: number): string {
  return `$${amount.toFixed(4)}`;
}

export function CostWarningBanner({ warning }: CostWarningBannerProps): React.JSX.Element {
  const { currentCostUsd, maxCostUsd, warningPct } = warning;
  return (
    <div className="flex items-start gap-3 rounded-md border border-yellow-500/40 bg-yellow-500/10 px-4 py-3 text-sm">
      <AlertTriangle className="h-4 w-4 text-yellow-600 mt-0.5 shrink-0" />
      <div className="space-y-1">
        <div className="font-medium text-yellow-700">
          Eval run approaching cost cap ({Math.round(warningPct * 100)}%)
        </div>
        <div className="text-xs text-muted-foreground">
          {formatUsd(currentCostUsd)} spent of {formatUsd(maxCostUsd)} cap
        </div>
      </div>
    </div>
  );
}
