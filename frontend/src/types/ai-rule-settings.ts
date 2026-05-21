export type AIRuleName =
  | "loss_plateau"
  | "loss_spike"
  | "grad_norm_exploding"
  | "eval_diverging"
  | "very_low_loss"
  | "high_truncation"
  | "memory_limit";

export interface AIRuleConfig {
  readonly enabled: boolean;
}

export type AIRuleSettings = Readonly<Record<AIRuleName, AIRuleConfig>>;

export interface AIRuleMetadata {
  readonly name: AIRuleName;
  readonly title: string;
  readonly description: string;
}

export const AI_RULE_ORDER: ReadonlyArray<AIRuleMetadata> = [
  {
    name: "loss_plateau",
    title: "Loss plateau",
    description: "Fires when eval/train loss changes less than 1% over the last 5 steps.",
  },
  {
    name: "loss_spike",
    title: "Loss spike",
    description: "Fires when train loss jumps more than 20% step-over-step.",
  },
  {
    name: "grad_norm_exploding",
    title: "Gradient norm exploding",
    description: "Fires when current grad_norm is 10× or more vs. the initial value.",
  },
  {
    name: "eval_diverging",
    title: "Eval loss diverging",
    description: "Fires when eval loss is climbing while train loss continues to drop.",
  },
  {
    name: "very_low_loss",
    title: "Very low loss",
    description: "Informational signal when training loss reaches below 0.1.",
  },
  {
    name: "high_truncation",
    title: "High truncation rate",
    description: "Fires when more than 20% of samples are truncated at max_seq_length.",
  },
  {
    name: "memory_limit",
    title: "Approaching memory limit",
    description: "Fires when GPU memory crosses 90% of the configured cap.",
  },
];
