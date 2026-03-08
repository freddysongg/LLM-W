import * as React from "react";
import type { TrainingConfig, TaskType } from "@/types/config";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface TrainingFormProps {
  readonly config: TrainingConfig;
  readonly datasetSize: number | null;
  readonly onChange: (updates: Partial<TrainingConfig>) => void;
}

export function TrainingForm({
  config,
  datasetSize,
  onChange,
}: TrainingFormProps): React.JSX.Element {
  const effectiveBatchSize = config.batchSize * config.gradientAccumulationSteps;
  const estimatedSteps =
    datasetSize !== null && effectiveBatchSize > 0
      ? Math.ceil((datasetSize / effectiveBatchSize) * config.epochs)
      : null;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Task</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="task-type">Task Type</Label>
            <Select
              value={config.taskType}
              onValueChange={(val) => onChange({ taskType: val as TaskType })}
            >
              <SelectTrigger id="task-type">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="sft">SFT (Supervised Fine-Tuning)</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Training Loop</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label htmlFor="epochs">Epochs</Label>
            <Input
              id="epochs"
              type="number"
              min="1"
              step="1"
              value={config.epochs}
              onChange={(e) => onChange({ epochs: Number(e.target.value) })}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="batch-size">Per-Device Batch Size</Label>
            <Input
              id="batch-size"
              type="number"
              min="1"
              step="1"
              value={config.batchSize}
              onChange={(e) => onChange({ batchSize: Number(e.target.value) })}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="grad-accum">Gradient Accumulation Steps</Label>
            <Input
              id="grad-accum"
              type="number"
              min="1"
              step="1"
              value={config.gradientAccumulationSteps}
              onChange={(e) => onChange({ gradientAccumulationSteps: Number(e.target.value) })}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="seed">Random Seed</Label>
            <Input
              id="seed"
              type="number"
              min="0"
              step="1"
              value={config.seed}
              onChange={(e) => onChange({ seed: Number(e.target.value) })}
            />
          </div>

          <div className="space-y-2 col-span-2">
            <Label>Effective Batch Size</Label>
            <div className="h-9 px-3 py-2 rounded-md border bg-muted text-sm text-muted-foreground">
              {effectiveBatchSize} (batch × accumulation)
            </div>
          </div>

          {estimatedSteps !== null && (
            <div className="space-y-2 col-span-2">
              <Label>Estimated Steps</Label>
              <div className="h-9 px-3 py-2 rounded-md border bg-muted text-sm text-muted-foreground">
                {estimatedSteps.toLocaleString()}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Optimization</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label htmlFor="learning-rate">Learning Rate</Label>
            <Input
              id="learning-rate"
              type="number"
              step="1e-6"
              min="0"
              value={config.learningRate}
              onChange={(e) => onChange({ learningRate: Number(e.target.value) })}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="weight-decay">Weight Decay</Label>
            <Input
              id="weight-decay"
              type="number"
              step="0.01"
              min="0"
              value={config.weightDecay}
              onChange={(e) => onChange({ weightDecay: Number(e.target.value) })}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="max-grad-norm">Max Gradient Norm</Label>
            <Input
              id="max-grad-norm"
              type="number"
              step="0.1"
              min="0"
              value={config.maxGradNorm}
              onChange={(e) => onChange({ maxGradNorm: Number(e.target.value) })}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Intervals</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label htmlFor="eval-steps">Eval Steps</Label>
            <Input
              id="eval-steps"
              type="number"
              min="1"
              step="1"
              value={config.evalSteps}
              onChange={(e) => onChange({ evalSteps: Number(e.target.value) })}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="save-steps">Save Steps</Label>
            <Input
              id="save-steps"
              type="number"
              min="1"
              step="1"
              value={config.saveSteps}
              onChange={(e) => onChange({ saveSteps: Number(e.target.value) })}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="logging-steps">Logging Steps</Label>
            <Input
              id="logging-steps"
              type="number"
              min="1"
              step="1"
              value={config.loggingSteps}
              onChange={(e) => onChange({ loggingSteps: Number(e.target.value) })}
            />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
