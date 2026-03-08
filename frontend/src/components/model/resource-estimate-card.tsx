import * as React from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import type { ResourceEstimate } from "@/types/model";

interface ResourceEstimateCardProps {
  readonly estimate: ResourceEstimate;
}

interface ResourceRowProps {
  readonly label: string;
  readonly value: string;
}

function ResourceRow({ label, value }: ResourceRowProps): React.JSX.Element {
  return (
    <div className="flex justify-between items-center py-1.5 border-b last:border-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-mono font-medium">{value}</span>
    </div>
  );
}

function formatGb(gb: number): string {
  return gb >= 1 ? `${gb.toFixed(1)} GB` : `${(gb * 1024).toFixed(0)} MB`;
}

export function ResourceEstimateCard({ estimate }: ResourceEstimateCardProps): React.JSX.Element {
  const { vram_gb, training_memory_gb, disk_gb } = estimate;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium">Resource Estimate</CardTitle>
      </CardHeader>
      <CardContent>
        <ResourceRow label="VRAM" value={formatGb(vram_gb)} />
        <ResourceRow label="Training Memory" value={formatGb(training_memory_gb)} />
        <ResourceRow label="Disk" value={formatGb(disk_gb)} />
      </CardContent>
    </Card>
  );
}
