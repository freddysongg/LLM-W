import * as React from "react";
import { parse as parseYaml, stringify as stringifyYaml } from "yaml";
import { useAppStore } from "@/stores/app-store";
import { useActiveConfig, useSaveConfig } from "@/hooks/useConfigs";
import { AdaptersForm } from "@/components/adapters/adapters-form";
import { TrainableParamsPreview } from "@/components/adapters/trainable-params-preview";
import { NoProjectSelected } from "@/components/shared/no-project-selected";
import type {
  AdaptersConfig,
  OptimizationConfig,
  QuantizationConfig,
  WorkbenchConfig,
} from "@/types/config";
import { Button } from "@/components/ui/button";

export default function AdaptersPage(): React.JSX.Element {
  const { activeProjectId } = useAppStore();
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
      return parseYaml(configVersion.yamlBlob) as WorkbenchConfig;
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
    saveConfig.mutate({
      request: {
        projectId: activeProjectId ?? "",
        yamlContent: stringifyYaml(updated),
        sourceTag: "user",
      },
    });
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
    <div className="p-6 max-w-2xl space-y-4 pb-20">
      <h1 className="text-xl font-semibold">Adapters &amp; Optimization</h1>

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

      {localAdapters && (
        <div className="fixed bottom-0 right-0 z-10 flex justify-end border-t border-border bg-background px-6 py-4 shadow-md w-full">
          <Button onClick={handleSave} disabled={saveConfig.isPending} size="sm">
            {saveConfig.isPending ? "Saving…" : "Save Config"}
          </Button>
        </div>
      )}
    </div>
  );
}
