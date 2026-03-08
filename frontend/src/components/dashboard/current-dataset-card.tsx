import * as React from "react";
import type { DatasetProfile } from "@/types/dataset";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface CurrentDatasetCardProps {
  readonly profile: DatasetProfile | undefined;
  readonly isLoading: boolean;
}

export function CurrentDatasetCard({
  profile,
  isLoading,
}: CurrentDatasetCardProps): React.JSX.Element {
  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Active Dataset</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">Loading...</CardContent>
      </Card>
    );
  }

  if (!profile) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Active Dataset</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">No dataset resolved.</CardContent>
      </Card>
    );
  }

  const { datasetId, source, splitCounts, totalRows } = profile;
  const trainSize = splitCounts.train ?? totalRows;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Active Dataset</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <div className="font-mono text-xs truncate" title={datasetId}>
          {datasetId}
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="text-xs">
            {source}
          </Badge>
        </div>
        <div className="text-xs text-muted-foreground">
          {totalRows.toLocaleString()} total rows &mdash; {trainSize.toLocaleString()} train
        </div>
      </CardContent>
    </Card>
  );
}
