import * as React from "react";
import { parse as parseYaml, stringify as stringifyYaml } from "yaml";
import { Check, RefreshCw } from "lucide-react";
import { useAppStore } from "@/stores/app-store";
import { useActiveConfig, useSaveConfig } from "@/hooks/useConfigs";
import { useModelArchitecture } from "@/hooks/useModelArchitecture";
import { AdaptersForm } from "@/components/adapters/adapters-form";
import { AdaptersPresetsPanel } from "@/components/adapters/adapters-presets-panel";
import type { AdaptersPresetValues } from "@/components/adapters/adapters-presets-panel";
import { TrainableParamsPreview } from "@/components/adapters/trainable-params-preview";
import { NoProjectSelected } from "@/components/shared/no-project-selected";
import { CopyForAI } from "@/components/shared/copy-for-ai";
import { buildAdaptersPrompt } from "@/lib/ai-copy-prompts";
import { normalizeYamlConfig, denormalizeYamlConfig } from "@/lib/yaml-config";
import type {
  AdaptersConfig,
  OptimizationConfig,
  QuantizationConfig,
  WorkbenchConfig,
} from "@/types/config";
import type { LayerNode, ModelArchitectureResponse } from "@/types/model";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/hooks/use-toast";

type AdaptersTab = "lora" | "quantization" | "memory";

const DEFAULT_HIDDEN_DIM = 1536;

function findEmbeddingDim(node: LayerNode): number | null {
  if (node.type.toLowerCase().includes("embedding") && node.shape && node.shape.length >= 2) {
    return node.shape[1];
  }
  for (const child of node.children ?? []) {
    const match = findEmbeddingDim(child);
    if (match !== null) return match;
  }
  return null;
}

function deriveHiddenDim({
  architecture,
}: {
  readonly architecture: ModelArchitectureResponse | undefined;
}): number {
  if (!architecture) return DEFAULT_HIDDEN_DIM;
  return findEmbeddingDim(architecture.tree) ?? DEFAULT_HIDDEN_DIM;
}

export default function AdaptersPage(): React.JSX.Element {
  const { activeProjectId } = useAppStore();
  const { toast } = useToast();
  const [activeTab, setActiveTab] = React.useState<AdaptersTab>("lora");
  const {
    data: configVersion,
    isLoading,
    error,
  } = useActiveConfig({ projectId: activeProjectId ?? "" });
  const saveConfig = useSaveConfig({ projectId: activeProjectId ?? "" });
  const { data: architecture } = useModelArchitecture({ projectId: activeProjectId ?? "" });

  const [localAdapters, setLocalAdapters] = React.useState<AdaptersConfig | null>(null);
  const [localOptimization, setLocalOptimization] = React.useState<OptimizationConfig | null>(null);
  const [localQuantization, setLocalQuantization] = React.useState<QuantizationConfig | null>(null);

  const parsedConfig = React.useMemo((): WorkbenchConfig | null => {
    if (!configVersion?.yamlBlob) return null;
    try {
      return normalizeYamlConfig<WorkbenchConfig>(parseYaml(configVersion.yamlBlob));
    } catch {
      return null;
    }
  }, [configVersion]);

  React.useEffect(() => {
    if (parsedConfig && !localAdapters) {
      setLocalAdapters({
        ...parsedConfig.adapters,
        targetModules: parsedConfig.adapters.targetModules ?? [],
      });
      setLocalOptimization(parsedConfig.optimization);
      setLocalQuantization(parsedConfig.quantization);
    }
  }, [parsedConfig, localAdapters]);

  const hiddenDim = React.useMemo(() => deriveHiddenDim({ architecture }), [architecture]);

  const handleSave = (): void => {
    if (!parsedConfig || !localAdapters || !localOptimization || !localQuantization) return;
    const updated: WorkbenchConfig = {
      ...parsedConfig,
      adapters: localAdapters,
      optimization: localOptimization,
      quantization: localQuantization,
    };
    saveConfig.mutate(
      {
        request: {
          projectId: activeProjectId ?? "",
          yamlContent: stringifyYaml(denormalizeYamlConfig(updated)),
          sourceTag: "user",
        },
      },
      {
        onSuccess: () =>
          toast({
            title: "Config saved",
            description: "Adapters & Optimization configuration saved successfully.",
          }),
        onError: () =>
          toast({
            title: "Save failed",
            description: "Failed to save adapters configuration.",
            variant: "destructive",
          }),
      },
    );
  };

  const handlePresetApply = ({
    adapters,
    optimization,
    quantization,
  }: AdaptersPresetValues): void => {
    if (Object.keys(adapters).length > 0) {
      setLocalAdapters((prev) => (prev ? { ...prev, ...adapters } : null));
    }
    if (Object.keys(optimization).length > 0) {
      setLocalOptimization((prev) => (prev ? { ...prev, ...optimization } : null));
    }
    if (Object.keys(quantization).length > 0) {
      setLocalQuantization((prev) => (prev ? { ...prev, ...quantization } : null));
    }
  };

  const handleResetToParsed = (): void => {
    if (!parsedConfig) return;
    setLocalAdapters({
      ...parsedConfig.adapters,
      targetModules: parsedConfig.adapters.targetModules ?? [],
    });
    setLocalOptimization(parsedConfig.optimization);
    setLocalQuantization(parsedConfig.quantization);
    toast({ title: "Reset", description: "Reverted to last saved configuration." });
  };

  if (!activeProjectId) {
    return (
      <NoProjectSelected
        pageTitle="Adapters & Optimization"
        description="Select a project on the Dashboard to configure its adapters and optimization settings."
      />
    );
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex h-14 items-center justify-between border-b border-hairline px-6">
        <div>
          <h1 className="font-mono text-[16px] font-semibold tracking-tight text-ink-1">
            Adapters &amp; Optimization
          </h1>
          <p className="font-mono text-[11px] text-ink-3">
            LoRA · Quantization · Memory strategies
          </p>
        </div>
        <div className="flex items-center gap-2">
          {localAdapters && localOptimization && localQuantization && (
            <CopyForAI
              buildPrompt={() =>
                buildAdaptersPrompt({
                  adapters: localAdapters,
                  optimization: localOptimization,
                  quantization: localQuantization,
                })
              }
            />
          )}
          {parsedConfig && (
            <Button variant="outline" size="sm" onClick={handleResetToParsed}>
              <RefreshCw className="size-3" aria-hidden="true" />
              Reset
            </Button>
          )}
          {localAdapters && (
            <Button
              variant="primary"
              size="sm"
              onClick={handleSave}
              disabled={saveConfig.isPending}
            >
              <Check className="size-3" aria-hidden="true" />
              {saveConfig.isPending ? "Saving…" : "Save"}
            </Button>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        {isLoading && <p className="font-mono text-[11px] text-ink-3">Loading config…</p>}
        {error && (
          <p className="font-mono text-[11px] text-[color:var(--danger)]">Failed to load config.</p>
        )}

        {localAdapters && localOptimization && localQuantization && (
          <div className="flex gap-6">
            <div className="flex-1 space-y-4">
              <TrainableParamsPreview adapters={localAdapters} projectId={activeProjectId} />
              <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as AdaptersTab)}>
                <TabsList>
                  <TabsTrigger value="lora">LoRA</TabsTrigger>
                  <TabsTrigger value="quantization">Quantization</TabsTrigger>
                  <TabsTrigger value="memory">Memory</TabsTrigger>
                </TabsList>

                <TabsContent value="lora">
                  <AdaptersForm
                    section="lora"
                    adapters={localAdapters}
                    optimization={localOptimization}
                    quantization={localQuantization}
                    onAdaptersChange={(updates) =>
                      setLocalAdapters((prev) => (prev ? { ...prev, ...updates } : null))
                    }
                    onOptimizationChange={(updates) =>
                      setLocalOptimization((prev) => (prev ? { ...prev, ...updates } : null))
                    }
                    onQuantizationChange={(updates) =>
                      setLocalQuantization((prev) => (prev ? { ...prev, ...updates } : null))
                    }
                    assumedHiddenDim={hiddenDim}
                  />
                </TabsContent>

                <TabsContent value="quantization">
                  <AdaptersForm
                    section="quantization"
                    adapters={localAdapters}
                    optimization={localOptimization}
                    quantization={localQuantization}
                    onAdaptersChange={(updates) =>
                      setLocalAdapters((prev) => (prev ? { ...prev, ...updates } : null))
                    }
                    onOptimizationChange={(updates) =>
                      setLocalOptimization((prev) => (prev ? { ...prev, ...updates } : null))
                    }
                    onQuantizationChange={(updates) =>
                      setLocalQuantization((prev) => (prev ? { ...prev, ...updates } : null))
                    }
                    assumedHiddenDim={hiddenDim}
                  />
                </TabsContent>

                <TabsContent value="memory">
                  <AdaptersForm
                    section="memory"
                    adapters={localAdapters}
                    optimization={localOptimization}
                    quantization={localQuantization}
                    onAdaptersChange={(updates) =>
                      setLocalAdapters((prev) => (prev ? { ...prev, ...updates } : null))
                    }
                    onOptimizationChange={(updates) =>
                      setLocalOptimization((prev) => (prev ? { ...prev, ...updates } : null))
                    }
                    onQuantizationChange={(updates) =>
                      setLocalQuantization((prev) => (prev ? { ...prev, ...updates } : null))
                    }
                    assumedHiddenDim={hiddenDim}
                  />
                </TabsContent>
              </Tabs>
            </div>

            <AdaptersPresetsPanel onApply={handlePresetApply} />
          </div>
        )}
      </div>
    </div>
  );
}
