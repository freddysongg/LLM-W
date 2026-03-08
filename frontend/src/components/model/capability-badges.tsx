import * as React from "react";
import { Badge } from "@/components/ui/badge";
import type { ModelProfile } from "@/types/model";

interface CapabilityBadgesProps {
  readonly profile: ModelProfile;
}

const FAMILY_TASK_MAP: Record<string, ReadonlyArray<string>> = {
  causal_lm: ["Text Generation", "Conversational", "SFT"],
  seq2seq: ["Summarization", "Translation", "SFT"],
  encoder_only: ["Embeddings", "Classification"],
};

const ADAPTER_METHODS = ["LoRA", "QLoRA"] as const;

const QUANT_MODES: Record<string, ReadonlyArray<string>> = {
  causal_lm: ["4-bit", "8-bit"],
  seq2seq: ["8-bit"],
  encoder_only: [],
};

export function CapabilityBadges({ profile }: CapabilityBadgesProps): React.JSX.Element {
  const { family } = profile;
  const tasks = FAMILY_TASK_MAP[family] ?? [];
  const quantModes = QUANT_MODES[family] ?? [];

  return (
    <div className="space-y-3">
      {tasks.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">Tasks</p>
          <div className="flex flex-wrap gap-1.5">
            {tasks.map((task) => (
              <Badge key={task} variant="secondary">
                {task}
              </Badge>
            ))}
          </div>
        </div>
      )}
      <div className="space-y-1">
        <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">
          Adapter Methods
        </p>
        <div className="flex flex-wrap gap-1.5">
          {ADAPTER_METHODS.map((method) => (
            <Badge key={method} variant="outline">
              {method}
            </Badge>
          ))}
        </div>
      </div>
      {quantModes.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">
            Quantization
          </p>
          <div className="flex flex-wrap gap-1.5">
            {quantModes.map((mode) => (
              <Badge key={mode} variant="outline">
                {mode}
              </Badge>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
