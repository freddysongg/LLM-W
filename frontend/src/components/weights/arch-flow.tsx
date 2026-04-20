import * as React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { ModelArchitectureResponse, LayerNode } from "@/types/model";
import { ArchStage, type ArchStageKind } from "@/components/weights/arch-stage";
import { ArchEndcap } from "@/components/weights/arch-endcap";
import { ArchWire } from "@/components/weights/arch-wire";
import { KVList } from "@/components/shared/kv-list";
import { cn } from "@/lib/utils";

type ArchStageId = "embed" | "layers" | "norm" | "head";

interface ArchStageDescriptor {
  readonly id: ArchStageId;
  readonly kind: ArchStageKind;
  readonly label: string;
  readonly sub: string;
  readonly params: string;
  readonly details: {
    readonly dtype: string;
    readonly shape: string | null;
    readonly notes: string;
  };
}

interface ArchFlowProps {
  readonly architecture: ModelArchitectureResponse;
  readonly selectedLayerIndex: number;
  readonly onSelectLayer: (layerIndex: number) => void;
  readonly dtype: string;
}

const STACK_TICK_COUNT = 14;

function formatParamCount(count: number | null): string {
  if (count === null) return "—";
  if (count >= 1_000_000_000) return `${(count / 1_000_000_000).toFixed(2)}B`;
  if (count >= 1_000_000) return `${(count / 1_000_000).toFixed(1)}M`;
  if (count >= 1_000) return `${(count / 1_000).toFixed(1)}K`;
  return String(count);
}

function findLayerStackNode(node: LayerNode): LayerNode | null {
  for (const child of node.children ?? []) {
    const grandChildren = child.children ?? [];
    if (grandChildren.length >= 2) {
      const sameType = grandChildren.every((g) => g.type === grandChildren[0].type);
      if (sameType) return child;
    }
    const deeper = findLayerStackNode(child);
    if (deeper) return deeper;
  }
  return null;
}

function findEmbeddingNode(node: LayerNode): LayerNode | null {
  if (node.type.toLowerCase().includes("embedding")) return node;
  for (const child of node.children ?? []) {
    const found = findEmbeddingNode(child);
    if (found) return found;
  }
  return null;
}

function findNormNode(node: LayerNode): LayerNode | null {
  if (node.type.toLowerCase().includes("norm") && !(node.children ?? []).length) return node;
  for (const child of node.children ?? []) {
    const found = findNormNode(child);
    if (found) return found;
  }
  return null;
}

function findHeadNode(node: LayerNode): LayerNode | null {
  for (const child of node.children ?? []) {
    if (child.name === "lm_head" || child.type.toLowerCase().includes("lmhead")) return child;
    const found = findHeadNode(child);
    if (found) return found;
  }
  return null;
}

function buildStageDescriptors({
  architecture,
  dtype,
}: {
  readonly architecture: ModelArchitectureResponse;
  readonly dtype: string;
}): ReadonlyArray<ArchStageDescriptor> {
  const tree = architecture.tree;
  const embedNode = findEmbeddingNode(tree);
  const stackNode = findLayerStackNode(tree);
  const normNode = findNormNode(tree);
  const headNode = findHeadNode(tree);

  const embedShape = embedNode?.shape ? `[${embedNode.shape.join(", ")}]` : null;
  const stackLayerCount = stackNode ? (stackNode.children ?? []).length : 0;

  return [
    {
      id: "embed",
      kind: "embed",
      label: embedNode?.name ?? "embed_tokens",
      sub: embedShape ?? "—",
      params: formatParamCount(embedNode?.params ?? null),
      details: {
        dtype,
        shape: embedShape,
        notes: "Token embedding lookup table. Shared with lm_head when weights are tied.",
      },
    },
    {
      id: "layers",
      kind: "stack",
      label: `layers × ${stackLayerCount || "N"}`,
      sub: stackNode?.type ?? "decoder blocks",
      params: formatParamCount(stackNode?.params ?? null),
      details: {
        dtype,
        shape: null,
        notes:
          "Residual stream through causal decoder blocks. Each block applies attention then mlp.",
      },
    },
    {
      id: "norm",
      kind: "norm",
      label: normNode?.name ?? "final_norm",
      sub: normNode?.type ?? "rms_norm",
      params: formatParamCount(normNode?.params ?? null),
      details: {
        dtype,
        shape: normNode?.shape ? `[${normNode.shape.join(", ")}]` : null,
        notes: "Final pre-head normalization. Stabilizes hidden state before projection.",
      },
    },
    {
      id: "head",
      kind: "head",
      label: headNode?.name ?? "lm_head",
      sub: "projection",
      params: formatParamCount(headNode?.params ?? null),
      details: {
        dtype,
        shape: headNode?.shape ? `[${headNode.shape.join(", ")}]` : null,
        notes: "Projects hidden state to vocabulary logits.",
      },
    },
  ];
}

interface StackStripProps {
  readonly layerCount: number;
  readonly selectedLayerIndex: number;
  readonly onSelectLayer: (layerIndex: number) => void;
}

function StackStrip({
  layerCount,
  selectedLayerIndex,
  onSelectLayer,
}: StackStripProps): React.JSX.Element {
  const tickCount = Math.min(STACK_TICK_COUNT, Math.max(1, layerCount));
  return (
    <div className="mt-2 flex gap-[3px] rounded-sm border border-hairline bg-surface-2 px-1 py-[5px]">
      {Array.from({ length: tickCount }, (_, tickIdx) => {
        const layerIdx =
          layerCount === 0
            ? tickIdx
            : Math.round((tickIdx / Math.max(1, tickCount - 1)) * (layerCount - 1));
        const isSelected = layerIdx === selectedLayerIndex;
        return (
          <button
            key={tickIdx}
            type="button"
            aria-label={`Select layer ${layerIdx}`}
            onClick={(event) => {
              event.stopPropagation();
              onSelectLayer(layerIdx);
            }}
            className={cn(
              "flex-1 rounded-[1px] transition-colors duration-[var(--dur-1)]",
              isSelected
                ? "h-3.5 self-center bg-ink-1"
                : "h-2.5 bg-[color-mix(in_oklch,var(--iris-3)_30%,transparent)] hover:bg-[color-mix(in_oklch,var(--iris-3)_55%,transparent)]",
            )}
          />
        );
      })}
    </div>
  );
}

export function ArchFlow({
  architecture,
  selectedLayerIndex,
  onSelectLayer,
  dtype,
}: ArchFlowProps): React.JSX.Element {
  const stages = React.useMemo(
    () => buildStageDescriptors({ architecture, dtype }),
    [architecture, dtype],
  );

  const initialStack = stages.find((s) => s.kind === "stack");
  const [selectedStageId, setSelectedStageId] = React.useState<ArchStageId>(
    initialStack?.id ?? stages[0].id,
  );

  const selectedStage = stages.find((s) => s.id === selectedStageId) ?? stages[0];
  const isStackSelected = selectedStage.kind === "stack";
  const stackNode = React.useMemo(() => findLayerStackNode(architecture.tree), [architecture]);
  const stackLayerCount = stackNode ? (stackNode.children ?? []).length : 0;

  return (
    <Card>
      <CardHeader>
        <div className="space-y-0.5">
          <CardTitle>Forward pass · computation graph</CardTitle>
          <p className="font-mono text-[11px] text-ink-3">
            {architecture.architecture_name} · params{" "}
            {(architecture.total_parameters / 1e9).toFixed(2)}B
          </p>
        </div>
        <Badge variant="iris" dot={false}>
          {dtype}
        </Badge>
      </CardHeader>

      <div className="flex items-stretch gap-0 overflow-x-auto px-4 pb-3 pt-5">
        <ArchEndcap label="input_ids" shape="[batch, seq]" />
        <ArchWire />
        {stages.map((stage, idx) => (
          <React.Fragment key={stage.id}>
            <ArchStage
              label={stage.label}
              sub={stage.sub}
              params={stage.params}
              kind={stage.kind}
              isSelected={selectedStageId === stage.id}
              onSelect={() => setSelectedStageId(stage.id)}
            >
              {stage.kind === "stack" ? (
                <StackStrip
                  layerCount={stackLayerCount}
                  selectedLayerIndex={selectedLayerIndex}
                  onSelectLayer={onSelectLayer}
                />
              ) : null}
            </ArchStage>
            {idx < stages.length - 1 ? <ArchWire /> : null}
          </React.Fragment>
        ))}
        <ArchWire />
        <ArchEndcap label="logits" shape="[batch, seq, vocab]" />
      </div>

      <CardContent className="border-t border-dashed border-hairline">
        {!isStackSelected ? (
          <div className="flex flex-col gap-3">
            <div className="flex items-center gap-3">
              <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-ink-3">
                selected stage
              </span>
              <span aria-hidden="true" className="h-px flex-1 bg-hairline" />
              <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-ink-3">
                {selectedStage.params} params
              </span>
            </div>
            <div className="grid gap-4 md:grid-cols-[220px_1fr]">
              <div className="rounded-md border border-hairline bg-[linear-gradient(180deg,var(--surface)_0%,var(--surface-2)_100%)] p-3 font-mono text-[14px] font-semibold tracking-[-0.01em] text-ink-1">
                {selectedStage.label}
              </div>
              <div className="space-y-2">
                <KVList
                  rows={[
                    { key: "dtype", value: selectedStage.details.dtype },
                    {
                      key: "shape",
                      value: selectedStage.details.shape ?? "—",
                    },
                  ]}
                />
                <p className="rounded-r-sm border-l-2 border-[color:var(--iris-3)] bg-surface-2 px-3 py-2 text-[12.5px] leading-[1.55] text-ink-2">
                  {selectedStage.details.notes}
                </p>
              </div>
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            <div className="flex items-center gap-3">
              <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-ink-3">
                inside a decoder block
              </span>
              <span aria-hidden="true" className="h-px flex-1 bg-hairline" />
              <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-ink-3">
                {stackLayerCount || "N"} layers · selected L{selectedLayerIndex}
              </span>
            </div>
            <div className="grid gap-3 md:grid-cols-[1fr_auto_1fr]">
              <div className="flex flex-col gap-2.5 rounded-md border border-hairline bg-surface p-3">
                <div className="flex items-center gap-2 font-mono text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-2">
                  <span
                    aria-hidden="true"
                    className="size-2 rounded-full bg-[color-mix(in_oklch,var(--iris-3)_65%,transparent)]"
                  />
                  attention sublayer
                </div>
                <ol className="flex flex-col gap-1.5">
                  {["input_layernorm", "{q,k,v}_proj", "rope · sdpa", "o_proj"].map((step, i) => (
                    <li
                      key={step}
                      className="flex items-center gap-2.5 rounded-sm border border-[color-mix(in_oklch,var(--iris-3)_30%,transparent)] bg-[color-mix(in_oklch,var(--iris-3)_10%,var(--surface))] px-2 py-1.5"
                    >
                      <span className="grid size-5 place-items-center rounded-full border border-hairline bg-surface-2 font-mono text-[10px] text-ink-2">
                        {i + 1}
                      </span>
                      <span className="font-mono text-[11.5px] text-ink-1">{step}</span>
                    </li>
                  ))}
                </ol>
              </div>
              <div className="hidden md:flex">
                <ArchWire />
              </div>
              <div className="flex flex-col gap-2.5 rounded-md border border-hairline bg-surface p-3">
                <div className="flex items-center gap-2 font-mono text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-2">
                  <span
                    aria-hidden="true"
                    className="size-2 rounded-full bg-[color-mix(in_oklch,var(--success)_65%,transparent)]"
                  />
                  mlp sublayer
                </div>
                <ol className="flex flex-col gap-1.5">
                  {["post_attention_layernorm", "{gate,up}_proj", "silu", "down_proj"].map(
                    (step, i) => (
                      <li
                        key={step}
                        className="flex items-center gap-2.5 rounded-sm border border-[color-mix(in_oklch,var(--success)_28%,transparent)] bg-[color-mix(in_oklch,var(--success)_8%,var(--surface))] px-2 py-1.5"
                      >
                        <span className="grid size-5 place-items-center rounded-full border border-hairline bg-surface-2 font-mono text-[10px] text-ink-2">
                          {i + 1}
                        </span>
                        <span className="font-mono text-[11.5px] text-ink-1">{step}</span>
                      </li>
                    ),
                  )}
                </ol>
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
