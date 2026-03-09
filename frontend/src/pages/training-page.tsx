import * as React from "react";
import { parse as parseYaml, stringify as stringifyYaml } from "yaml";
import { useAppStore } from "@/stores/app-store";
import { useActiveConfig, useSaveConfig } from "@/hooks/useConfigs";
import { TrainingForm } from "@/components/training/training-form";
import { TrainingPresetsPanel } from "@/components/training/training-presets-panel";
import { NoProjectSelected } from "@/components/shared/no-project-selected";
import { CopyForAI } from "@/components/shared/copy-for-ai";
import { buildTrainingPrompt } from "@/lib/ai-copy-prompts";
import { normalizeYamlConfig, denormalizeYamlConfig } from "@/lib/yaml-config";
import type { TrainingConfig, WorkbenchConfig } from "@/types/config";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";

export default function TrainingPage(): React.JSX.Element {
  const { activeProjectId } = useAppStore();
  const {
    data: configVersion,
    isLoading,
    error,
  } = useActiveConfig({
    projectId: activeProjectId ?? "",
  });
  const saveConfig = useSaveConfig({ projectId: activeProjectId ?? "" });
  const { toast } = useToast();

  const [localTraining, setLocalTraining] = React.useState<TrainingConfig | null>(null);

  const parsedConfig = React.useMemo((): WorkbenchConfig | null => {
    if (!configVersion?.yamlBlob) return null;
    try {
      return normalizeYamlConfig<WorkbenchConfig>(parseYaml(configVersion.yamlBlob));
    } catch {
      return null;
    }
  }, [configVersion]);

  React.useEffect(() => {
    if (parsedConfig?.training && !localTraining) {
      setLocalTraining(parsedConfig.training);
    }
  }, [parsedConfig, localTraining]);

  const handleChange = (updates: Partial<TrainingConfig>): void => {
    setLocalTraining((prev) => (prev ? { ...prev, ...updates } : null));
  };

  const handleSave = (): void => {
    if (!parsedConfig || !localTraining || !configVersion) return;
    const updated: WorkbenchConfig = { ...parsedConfig, training: localTraining };
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
            description: "Training configuration saved successfully.",
          });
        },
        onError: () => {
          toast({
            title: "Save failed",
            description: "Failed to save training configuration.",
            variant: "destructive",
          });
        },
      },
    );
  };

  if (!activeProjectId) {
    return (
      <NoProjectSelected
        pageTitle="Training"
        description="Select a project on the Dashboard to configure its training settings."
      />
    );
  }

  return (
    <div className="p-6 flex gap-8 items-start">
      <div className="flex-1 max-w-2xl space-y-4">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold">Training</h1>
          <div className="flex items-center gap-2">
            {localTraining && parsedConfig && (
              <CopyForAI
                buildPrompt={() =>
                  buildTrainingPrompt({
                    training: localTraining,
                    optimization: parsedConfig.optimization,
                  })
                }
              />
            )}
            {localTraining && (
              <Button onClick={handleSave} disabled={saveConfig.isPending} size="sm">
                {saveConfig.isPending ? "Saving…" : "Save Config"}
              </Button>
            )}
          </div>
        </div>

        {isLoading && <div className="text-sm text-muted-foreground">Loading config…</div>}
        {error && <div className="text-sm text-destructive">Failed to load config.</div>}

        {localTraining && (
          <TrainingForm config={localTraining} datasetSize={null} onChange={handleChange} />
        )}
      </div>

      {localTraining && <TrainingPresetsPanel onApply={handleChange} />}
    </div>
  );
}
