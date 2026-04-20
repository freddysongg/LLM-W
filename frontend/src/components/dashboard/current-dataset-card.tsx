import * as React from "react";
import type { DatasetProfile } from "@/types/dataset";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { KVList } from "@/components/shared/kv-list";
import type { KVRow } from "@/components/shared/kv-list";

interface CurrentDatasetCardProps {
  readonly profile: DatasetProfile | undefined;
  readonly isLoading: boolean;
}

function formatCount(count: number | null): string {
  if (count === null) return "—";
  return count.toLocaleString();
}

function avgTokensLabel(profile: DatasetProfile): string {
  if (profile.tokenStats === null) return "—";
  return `${Math.round(profile.tokenStats.mean)}`;
}

function buildRows(profile: DatasetProfile): ReadonlyArray<KVRow> {
  const { datasetId, splitCounts, format, totalRows } = profile;
  const trainCount = splitCounts.train ?? totalRows;
  const evalCount = splitCounts.validation ?? splitCounts.test ?? null;
  return [
    { key: "Dataset", value: datasetId },
    { key: "Train", value: formatCount(trainCount) },
    { key: "Eval", value: formatCount(evalCount) },
    { key: "Format", value: format },
    { key: "Avg tokens", value: avgTokensLabel(profile) },
  ];
}

export function CurrentDatasetCard({
  profile,
  isLoading,
}: CurrentDatasetCardProps): React.JSX.Element {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Current dataset</CardTitle>
        {profile ? <Badge dot={false}>{profile.source}</Badge> : null}
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="font-mono text-[11px] text-ink-3">Loading…</div>
        ) : profile ? (
          <KVList rows={buildRows(profile)} dense />
        ) : (
          <div className="font-mono text-[11px] text-ink-3">No dataset resolved.</div>
        )}
      </CardContent>
    </Card>
  );
}
