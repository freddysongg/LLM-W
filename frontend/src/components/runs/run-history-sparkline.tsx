import * as React from "react";

import { Sparkline } from "@/components/shared/sparkline";
import type { RunSummary } from "@/types/run-summary";

interface RunHistorySparklineProps {
  readonly summary: RunSummary;
}

export function RunHistorySparkline({ summary }: RunHistorySparklineProps): React.JSX.Element {
  const { trainLossSparkline, finalTrainLoss, finalEvalLoss, stepCount, wallClockMs } = summary;
  return (
    <div className="flex items-center gap-3">
      <div className="h-6 w-28">
        <Sparkline data={trainLossSparkline} height={24} />
      </div>
      <div className="flex gap-3 font-mono text-[11px] tabular-nums text-muted-foreground">
        <span>
          train{" "}
          <span className="text-foreground">
            {finalTrainLoss !== null ? finalTrainLoss.toFixed(4) : "—"}
          </span>
        </span>
        <span>
          eval{" "}
          <span className="text-foreground">
            {finalEvalLoss !== null ? finalEvalLoss.toFixed(4) : "—"}
          </span>
        </span>
        <span>
          {stepCount} steps · {(wallClockMs / 1000).toFixed(0)}s
        </span>
      </div>
    </div>
  );
}
