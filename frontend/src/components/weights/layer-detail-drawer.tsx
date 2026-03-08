import * as React from "react";
import type { LayerDetailResponse } from "@/types/model";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";

interface LayerDetailDrawerProps {
  readonly layerDetail: LayerDetailResponse | null;
  readonly isLoading: boolean;
  readonly onClose: () => void;
}

function formatParamCount(params: number): string {
  if (params >= 1e9) return `${(params / 1e9).toFixed(2)}B`;
  if (params >= 1e6) return `${(params / 1e6).toFixed(2)}M`;
  if (params >= 1e3) return `${(params / 1e3).toFixed(1)}K`;
  return String(params);
}

export function LayerDetailDrawer({
  layerDetail,
  isLoading,
  onClose,
}: LayerDetailDrawerProps): React.JSX.Element {
  const isOpen = isLoading || layerDetail !== null;

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="font-mono text-sm truncate">
            {layerDetail?.name ?? "Loading…"}
          </DialogTitle>
        </DialogHeader>

        {isLoading && (
          <div className="py-8 text-center text-sm text-muted-foreground">Loading layer…</div>
        )}

        {!isLoading && layerDetail && (
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">Type</span>
              <Badge variant="outline" className="font-mono text-xs">
                {layerDetail.type}
              </Badge>
              <Badge variant={layerDetail.trainable ? "default" : "secondary"} className="text-xs">
                {layerDetail.trainable ? "trainable" : "frozen"}
              </Badge>
            </div>

            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <p className="text-xs text-muted-foreground mb-0.5">Parameters</p>
                <p className="font-mono font-medium">{formatParamCount(layerDetail.params)}</p>
              </div>

              {layerDetail.dtype && (
                <div>
                  <p className="text-xs text-muted-foreground mb-0.5">dtype</p>
                  <p className="font-mono font-medium">{layerDetail.dtype}</p>
                </div>
              )}

              {layerDetail.shape && layerDetail.shape.length > 0 && (
                <div className="col-span-2">
                  <p className="text-xs text-muted-foreground mb-0.5">Shape</p>
                  <p className="font-mono font-medium">[{layerDetail.shape.join(", ")}]</p>
                </div>
              )}
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
