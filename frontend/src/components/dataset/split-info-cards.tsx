import * as React from "react";
import type { SplitCounts } from "@/types/dataset";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface SplitInfoCardsProps {
  readonly splitCounts: SplitCounts;
  readonly totalRows: number;
}

interface SplitCardProps {
  readonly label: string;
  readonly count: number | null;
}

function SplitCard({ label, count }: SplitCardProps): React.JSX.Element {
  return (
    <Card>
      <CardHeader className="pb-1 pt-3 px-4">
        <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
          {label}
        </CardTitle>
      </CardHeader>
      <CardContent className="px-4 pb-3">
        {count !== null ? (
          <span className="text-2xl font-semibold tabular-nums">{count.toLocaleString()}</span>
        ) : (
          <span className="text-sm text-muted-foreground">—</span>
        )}
        {count !== null && <span className="ml-1 text-xs text-muted-foreground">rows</span>}
      </CardContent>
    </Card>
  );
}

export function SplitInfoCards({ splitCounts, totalRows }: SplitInfoCardsProps): React.JSX.Element {
  return (
    <div className="grid grid-cols-4 gap-3">
      <Card>
        <CardHeader className="pb-1 pt-3 px-4">
          <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
            Total
          </CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-3">
          <span className="text-2xl font-semibold tabular-nums">{totalRows.toLocaleString()}</span>
          <span className="ml-1 text-xs text-muted-foreground">rows</span>
        </CardContent>
      </Card>
      <SplitCard label="Train" count={splitCounts.train} />
      <SplitCard label="Validation" count={splitCounts.validation} />
      <SplitCard label="Test" count={splitCounts.test} />
    </div>
  );
}
