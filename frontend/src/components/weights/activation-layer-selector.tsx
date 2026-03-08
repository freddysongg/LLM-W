import * as React from "react";

interface ActivationLayerSelectorProps {
  readonly availableLayers: ReadonlyArray<string>;
  readonly selectedLayers: ReadonlyArray<string>;
  readonly onToggleLayer: (layerName: string) => void;
}

export function ActivationLayerSelector({
  availableLayers,
  selectedLayers,
  onToggleLayer,
}: ActivationLayerSelectorProps): React.JSX.Element {
  if (availableLayers.length === 0) {
    return (
      <div className="py-4 text-xs text-muted-foreground">
        No layers available. Resolve a model first.
      </div>
    );
  }

  const selectedSet = new Set(selectedLayers);

  return (
    <div className="space-y-1.5">
      <label className="text-xs font-medium text-muted-foreground">
        Layers to capture ({selectedLayers.length} selected)
      </label>
      <div className="border rounded-md overflow-y-auto max-h-40 p-1">
        {availableLayers.map((layerName) => {
          const isChecked = selectedSet.has(layerName);
          return (
            <label
              key={layerName}
              className="flex items-center gap-2 px-2 py-1 rounded hover:bg-muted/50 cursor-pointer"
            >
              <input
                type="checkbox"
                checked={isChecked}
                onChange={() => onToggleLayer(layerName)}
                className="h-3.5 w-3.5 accent-primary"
              />
              <span className="font-mono text-xs truncate">{layerName}</span>
            </label>
          );
        })}
      </div>
    </div>
  );
}
