import * as React from "react";
import { parse as parseYaml, stringify as stringifyYaml } from "yaml";
import { useAppStore } from "@/stores/app-store";
import { useActiveConfig, useSaveConfig } from "@/hooks/useConfigs";
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
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";

export default function AdaptersPage(): React.JSX.Element {
  const { activeProjectId } = useAppStore();
  const { toast } = useToast();
  const {
    data: configVersion,
    isLoading,
    error,
  } = useActiveConfig({
    projectId: activeProjectId ?? "",
  });
  const saveConfig = useSaveConfig({ projectId: activeProjectId ?? "" });

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
        onSuccess: () => {
          toast({
            title: "Config saved",
            description: "Adapters & Optimization configuration saved successfully.",
          });
        },
        onError: () => {
          toast({
            title: "Save failed",
            description: "Failed to save adapters configuration.",
            variant: "destructive",
          });
        },
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

  if (!activeProjectId) {
    return (
      <NoProjectSelected
        pageTitle="Adapters & Optimization"
        description="Select a project on the Dashboard to configure its adapters and optimization settings."
      />
    );
  }

  return (
    <div className="p-6 flex gap-8 items-start">
      <div className="flex-1 max-w-2xl space-y-4">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold">Adapters &amp; Optimization</h1>
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
            {localAdapters && (
              <Button onClick={handleSave} disabled={saveConfig.isPending} size="sm">
                {saveConfig.isPending ? "Saving…" : "Save Config"}
              </Button>
            )}
          </div>
        </div>

        {isLoading && <div className="text-sm text-muted-foreground">Loading config…</div>}
        {error && <div className="text-sm text-destructive">Failed to load config.</div>}

        {localAdapters && localOptimization && localQuantization && (
          <>
            <TrainableParamsPreview adapters={localAdapters} projectId={activeProjectId} />
            <AdaptersForm
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
            />
          </>
        )}
      </div>

      {localAdapters && <AdaptersPresetsPanel onApply={handlePresetApply} />}
    </div>
  );
}
