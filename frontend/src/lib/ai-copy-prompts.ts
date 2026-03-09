import type { ModelArchitectureResponse, LayerNode, ModelProfile } from "@/types/model";
import type {
  TrainingConfig,
  OptimizationConfig,
  AdaptersConfig,
  QuantizationConfig,
} from "@/types/config";

export interface BuildModelPromptParams {
  readonly profile: ModelProfile;
  readonly architecture: ModelArchitectureResponse;
}

export interface BuildTrainingPromptParams {
  readonly training: TrainingConfig;
  readonly optimization: OptimizationConfig;
}

export interface BuildAdaptersPromptParams {
  readonly adapters: AdaptersConfig;
  readonly optimization: OptimizationConfig;
  readonly quantization: QuantizationConfig;
}

export interface BuildArchitecturePromptParams {
  readonly architecture: ModelArchitectureResponse;
}

function capTreeDepth({ node, maxDepth }: { node: LayerNode; maxDepth: number }): LayerNode {
  if (maxDepth <= 0) {
    return { ...node, children: null };
  }
  return {
    ...node,
    children: node.children
      ? node.children.map((child) => capTreeDepth({ node: child, maxDepth: maxDepth - 1 }))
      : null,
  };
}

export function buildModelPrompt({ profile, architecture }: BuildModelPromptParams): string {
  const cappedTree = capTreeDepth({ node: architecture.tree, maxDepth: 3 });
  const context = { profile, architecture: { ...architecture, tree: cappedTree } };
  return (
    `[SYSTEM PROMPT]\n` +
    `You are an LLM model advisor. The user has loaded a model into their fine-tuning workbench. ` +
    `Help them understand what this model is — its architecture family, parameter count, memory and disk requirements, ` +
    `context length, vocabulary size, dtype, and what tasks it is suited for. ` +
    `Explain each field in plain terms and highlight anything notable about this specific model.\n\n` +
    `[CONTEXT]\n${JSON.stringify(context, null, 2)}`
  );
}

export function buildTrainingPrompt({ training, optimization }: BuildTrainingPromptParams): string {
  const context = { training, optimization };
  return (
    `[SYSTEM PROMPT]\n` +
    `You are an LLM fine-tuning configuration advisor. The user is setting up a supervised fine-tuning run. ` +
    `Help them understand what each setting controls, whether their values are sensible for a typical SFT run, ` +
    `and flag anything that might cause instability, slow training, or poor convergence.\n\n` +
    `[CONTEXT]\n${JSON.stringify(context, null, 2)}`
  );
}

export function buildAdaptersPrompt({
  adapters,
  optimization,
  quantization,
}: BuildAdaptersPromptParams): string {
  const context = { adapters, optimization, quantization };
  return (
    `[SYSTEM PROMPT]\n` +
    `You are an LLM adapter and quantization expert. The user is configuring parameter-efficient fine-tuning ` +
    `with LoRA/QLoRA along with optimizer and quantization settings. Explain what each setting does, ` +
    `whether the combination is coherent and efficient, and suggest any adjustments to improve training quality.\n\n` +
    `[CONTEXT]\n${JSON.stringify(context, null, 2)}`
  );
}

export function buildArchitecturePrompt({ architecture }: BuildArchitecturePromptParams): string {
  const cappedTree = capTreeDepth({ node: architecture.tree, maxDepth: 3 });
  const context = { ...architecture, tree: cappedTree };
  return (
    `[SYSTEM PROMPT]\n` +
    `You are an LLM architecture expert. The user is inspecting the internal structure of a model in their ` +
    `fine-tuning workbench. Below is the layer tree showing module names, types, parameter counts, trainability, ` +
    `and dtypes down to the projection layer level. Help them understand the structure, what each module type does, ` +
    `which parameters are trainable vs frozen, and how the architecture relates to the model capabilities.\n\n` +
    `[CONTEXT]\n${JSON.stringify(context, null, 2)}`
  );
}
