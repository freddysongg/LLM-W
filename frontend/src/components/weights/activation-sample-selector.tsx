import * as React from "react";
import { Button } from "@/components/ui/button";

interface ActivationSampleSelectorProps {
  readonly sampleInput: string;
  readonly onSampleInputChange: (value: string) => void;
  readonly onCapture: () => void;
  readonly isCapturing: boolean;
  readonly hasLayersSelected: boolean;
}

export function ActivationSampleSelector({
  sampleInput,
  onSampleInputChange,
  onCapture,
  isCapturing,
  hasLayersSelected,
}: ActivationSampleSelectorProps): React.JSX.Element {
  return (
    <div className="space-y-2">
      <label className="text-xs font-medium text-muted-foreground">Sample Input</label>
      <textarea
        value={sampleInput}
        onChange={(e) => onSampleInputChange(e.target.value)}
        placeholder="Enter text to use as sample input for activation capture…"
        className="w-full h-20 px-3 py-2 text-sm border rounded-md bg-background resize-none focus:outline-none focus:ring-2 focus:ring-ring"
        disabled={isCapturing}
      />
      <Button
        size="sm"
        onClick={onCapture}
        disabled={isCapturing || !sampleInput.trim() || !hasLayersSelected}
      >
        {isCapturing ? "Capturing…" : "Capture Activations"}
      </Button>
      {!hasLayersSelected && (
        <p className="text-xs text-muted-foreground">Select at least one layer below.</p>
      )}
    </div>
  );
}
