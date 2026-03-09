import * as React from "react";
import type { AdaptersConfig, OptimizationConfig, QuantizationConfig } from "@/types/config";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export interface AdaptersPresetValues {
  readonly adapters: Partial<AdaptersConfig>;
  readonly optimization: Partial<OptimizationConfig>;
  readonly quantization: Partial<QuantizationConfig>;
}

interface AdaptersPreset {
  readonly name: string;
  readonly description: string;
  readonly values: AdaptersPresetValues;
}

const ADAPTERS_PRESETS: ReadonlyArray<AdaptersPreset> = [
  {
    name: "LoRA Minimal",
    description: "Low-rank LoRA on attention projections only — fast training, small adapter size.",
    values: {
      adapters: {
        enabled: true,
        type: "lora",
        rank: 8,
        alpha: 16,
        dropout: 0.1,
        targetModules: ["q_proj", "v_proj"],
        bias: "none",
        taskType: "CAUSAL_LM",
      },
      optimization: {},
      quantization: { enabled: false },
    },
  },
  {
    name: "QLoRA 4-bit",
    description:
      "4-bit quantized LoRA with NF4 and double quantization — fits 13B+ models on 12 GB VRAM.",
    values: {
      adapters: {
        enabled: true,
        type: "qlora",
        rank: 16,
        alpha: 32,
        dropout: 0.05,
        targetModules: ["q_proj", "k_proj", "v_proj", "o_proj"],
        bias: "none",
        taskType: "CAUSAL_LM",
      },
      optimization: {
        optimizer: "paged_adamw_8bit",
        gradientCheckpointing: true,
        mixedPrecision: "bf16",
      },
      quantization: {
        enabled: true,
        mode: "4bit",
        computeDtype: "bfloat16",
        quantType: "nf4",
        doubleQuant: true,
      },
    },
  },
  {
    name: "Full LoRA",
    description:
      "Higher rank across all projection layers — maximum expressiveness for complex tasks.",
    values: {
      adapters: {
        enabled: true,
        type: "lora",
        rank: 32,
        alpha: 64,
        dropout: 0.1,
        targetModules: [
          "q_proj",
          "k_proj",
          "v_proj",
          "o_proj",
          "gate_proj",
          "up_proj",
          "down_proj",
        ],
        bias: "none",
        taskType: "CAUSAL_LM",
      },
      optimization: {},
      quantization: { enabled: false },
    },
  },
];

interface AdaptersPresetsPanelProps {
  readonly onApply: (values: AdaptersPresetValues) => void;
}

export function AdaptersPresetsPanel({ onApply }: AdaptersPresetsPanelProps): React.JSX.Element {
  return (
    <aside className="w-60 shrink-0 space-y-3">
      <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide px-1">
        Presets
      </p>
      {ADAPTERS_PRESETS.map((preset) => (
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
