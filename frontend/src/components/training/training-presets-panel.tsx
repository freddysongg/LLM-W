import * as React from "react";
import type { TrainingConfig } from "@/types/config";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface TrainingPreset {
  readonly name: string;
  readonly description: string;
  readonly values: Partial<TrainingConfig>;
}

const TRAINING_PRESETS: ReadonlyArray<TrainingPreset> = [
  {
    name: "Fast Convergence",
    description: "Higher LR with short warmup — best for quick iteration on small datasets.",
    values: {
      epochs: 3,
      batchSize: 4,
      gradientAccumulationSteps: 2,
      learningRate: 3e-4,
      weightDecay: 0.01,
      maxGradNorm: 1.0,
      evalSteps: 100,
      saveSteps: 100,
      loggingSteps: 10,
      seed: 42,
    },
  },
  {
    name: "Memory Efficient",
    description:
      "Minimal batch size with high gradient accumulation for large models on limited VRAM.",
    values: {
      epochs: 2,
      batchSize: 1,
      gradientAccumulationSteps: 16,
      learningRate: 2e-4,
      weightDecay: 0.0,
      maxGradNorm: 1.0,
      evalSteps: 200,
      saveSteps: 200,
      loggingSteps: 25,
      seed: 42,
    },
  },
  {
    name: "Stable Baseline",
    description: "Conservative LR and steady accumulation — reliable results with minimal tuning.",
    values: {
      epochs: 5,
      batchSize: 2,
      gradientAccumulationSteps: 4,
      learningRate: 1e-4,
      weightDecay: 0.01,
      maxGradNorm: 1.0,
      evalSteps: 250,
      saveSteps: 250,
      loggingSteps: 25,
      seed: 42,
    },
  },
];

interface TrainingPresetsPanelProps {
  readonly onApply: (values: Partial<TrainingConfig>) => void;
}

export function TrainingPresetsPanel({ onApply }: TrainingPresetsPanelProps): React.JSX.Element {
  return (
    <aside className="w-60 shrink-0 space-y-3">
      <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide px-1">
        Presets
      </p>
      {TRAINING_PRESETS.map((preset) => (
        <Card key={preset.name}>
          <CardHeader className="pb-2 pt-4 px-4">
            <CardTitle className="text-sm">{preset.name}</CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4 space-y-3">
            <p className="text-xs text-muted-foreground leading-relaxed">{preset.description}</p>
            <Button
              size="sm"
              variant="outline"
              className="w-full text-xs h-7"
              onClick={() => onApply(preset.values)}
            >
              Apply
            </Button>
          </CardContent>
        </Card>
      ))}
    </aside>
  );
}
