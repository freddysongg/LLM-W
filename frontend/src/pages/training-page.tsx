import * as React from "react";
import { parse as parseYaml, stringify as stringifyYaml } from "yaml";
import { useAppStore } from "@/stores/app-store";
import { useActiveConfig, useSaveConfig } from "@/hooks/useConfigs";
import { TrainingForm } from "@/components/training/training-form";
import { NoProjectSelected } from "@/components/shared/no-project-selected";
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
      return parseYaml(configVersion.yamlBlob) as WorkbenchConfig;
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
          yamlContent: stringifyYaml(updated),
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
    <div className="p-6 max-w-2xl space-y-4 pb-20">
      <h1 className="text-xl font-semibold">Training</h1>

      {isLoading && <div className="text-sm text-muted-foreground">Loading config…</div>}
      {error && <div className="text-sm text-destructive">Failed to load config.</div>}

      {localTraining && (
        <TrainingForm config={localTraining} datasetSize={null} onChange={handleChange} />
      )}

      {localTraining && (
        <div className="fixed bottom-0 right-0 z-10 flex justify-end border-t border-border bg-background px-6 py-4 shadow-md w-full">
          <Button onClick={handleSave} disabled={saveConfig.isPending} size="sm">
            {saveConfig.isPending ? "Saving…" : "Save Config"}
          </Button>
        </div>
      )}
    </div>
  );
}
