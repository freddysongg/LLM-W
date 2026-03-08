import * as React from "react";
import type { LayerDetailResponse } from "@/types/model";

interface TensorEditorProps {
  readonly layerDetail: LayerDetailResponse | null;
  readonly isExpertMode: boolean;
}

export function TensorEditor({ layerDetail, isExpertMode }: TensorEditorProps): React.JSX.Element {
  if (!isExpertMode) {
    return (
      <div className="py-4 text-sm text-muted-foreground">
        Enable Expert Edit Mode to access tensor editing.
      </div>
    );
  }

  if (!layerDetail) {
    return (
      <div className="py-4 text-sm text-muted-foreground">
        Select a layer from the Architecture tab to edit its parameters.
      </div>
    );
  }

  const { name, type, params, trainable, dtype, shape } = layerDetail;

  return (
    <div className="space-y-4">
      <div className="p-3 border rounded-md bg-muted/30 space-y-2">
        <div className="flex items-center gap-2">
          <span className="font-mono text-sm font-medium">{name}</span>
          <span className="text-xs text-muted-foreground">{type}</span>
        </div>
        <div className="grid grid-cols-3 gap-3 text-xs">
          <div>
            <p className="text-muted-foreground">Parameters</p>
            <p className="font-mono">{params.toLocaleString()}</p>
          </div>
          <div>
            <p className="text-muted-foreground">dtype</p>
            <p className="font-mono">{dtype ?? "—"}</p>
          </div>
          {shape && (
            <div>
              <p className="text-muted-foreground">Shape</p>
              <p className="font-mono">[{shape.join(", ")}]</p>
            </div>
          )}
        </div>
      </div>

      {!trainable && (
        <div className="p-3 border border-orange-400/30 bg-orange-50/50 dark:bg-orange-950/20 rounded-md text-xs text-orange-700 dark:text-orange-300">
          This layer is frozen. Editing frozen parameters is not currently supported.
        </div>
      )}

      {trainable && (
        <div className="space-y-2">
          <p className="text-xs font-medium">Tensor editing</p>
          <div className="p-4 border-2 border-dashed rounded-md text-center space-y-2">
            <p className="text-xs text-muted-foreground">
              Direct tensor editing is not yet available in this version.
            </p>
            <p className="text-xs text-muted-foreground">
              Use training configuration to adjust {name} via LoRA adapter settings.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
