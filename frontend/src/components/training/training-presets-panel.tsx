import * as React from "react";
import type { TrainingConfig } from "@/types/config";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface TrainingPreset {
  readonly name: string;
  readonly description: string;
  readonly values: Partial<TrainingConfig>;
}

const TRAINING_PRESETS: ReadonlyArray<TrainingPreset> = [
  {
    name: "Fast convergence",
    description: "Higher LR with short warmup — best for quick iteration.",
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
    name: "Memory efficient",
    description: "Minimal batch size, high grad accumulation for large models.",
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
    name: "Stable baseline",
    description: "Conservative LR and steady accumulation.",
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
    <Card>
      <CardHeader>
        <CardTitle>Presets</CardTitle>
        <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-ink-3">
          quick apply
        </span>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {TRAINING_PRESETS.map((preset) => (
          <div
            key={preset.name}
            className="flex flex-col gap-2 rounded-md border border-hairline bg-surface-2 px-3 py-2.5"
          >
            <div className="text-[12.5px] font-medium text-ink-1">{preset.name}</div>
            <div className="font-mono text-[10.5px] leading-snug text-ink-3">
              {preset.description}
            </div>
            <Button
              size="sm"
              variant="outline"
              className="self-start"
              onClick={() => onApply(preset.values)}
            >
              Apply
            </Button>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
