import * as React from "react";
import { useLayerDetail } from "@/hooks/useModelArchitecture";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";

interface LayerDetailPanelProps {
  readonly projectId: string;
  readonly layerName: string;
}

function formatParams(params: number): string {
  if (params >= 1_000_000) return `${(params / 1_000_000).toFixed(2)}M`;
  if (params >= 1_000) return `${(params / 1_000).toFixed(1)}K`;
  return String(params);
}

function InfoRow({
  label,
  value,
}: {
  readonly label: string;
  readonly value: React.ReactNode;
}): React.JSX.Element {
  return (
    <div className="flex justify-between items-start gap-2 py-1.5">
      <span className="text-xs text-muted-foreground shrink-0">{label}</span>
      <span className="text-xs font-mono text-right break-all">{value}</span>
    </div>
  );
}

export function LayerDetailPanel({
  projectId,
  layerName,
}: LayerDetailPanelProps): React.JSX.Element {
  const { data: layer, isLoading } = useLayerDetail({ projectId, layerName });

  if (isLoading) {
    return <p className="text-sm text-muted-foreground p-4">Loading…</p>;
  }

  if (!layer) {
    return <p className="text-sm text-muted-foreground p-4">Layer not found.</p>;
  }

  const { name, type, params, trainable, dtype, shape } = layer;

  return (
    <div className="space-y-3">
      <div>
        <p className="text-xs text-muted-foreground mb-0.5">Layer</p>
        <p className="text-sm font-mono break-all">{name}</p>
      </div>

      <Separator />

      <div className="space-y-0.5">
        <InfoRow label="Module type" value={type} />
        <InfoRow label="Parameters" value={formatParams(params)} />
        {dtype && <InfoRow label="Dtype" value={dtype} />}
        {shape && shape.length > 0 && <InfoRow label="Shape" value={`[${shape.join(", ")}]`} />}
      </div>

      <Separator />

      <div className="flex items-center gap-2">
        <Badge variant={trainable ? "default" : "secondary"}>
          {trainable ? "Trainable" : "Frozen"}
        </Badge>
      </div>
    </div>
  );
}
