import * as React from "react";
import { parse as parseYaml, stringify as stringifyYaml } from "yaml";
import { useAppStore } from "@/stores/app-store";
import { useActiveConfig, useSaveConfig } from "@/hooks/useConfigs";
import { TrainingForm } from "@/components/training/training-form";
import type { TrainingConfig, WorkbenchConfig } from "@/types/config";
import { Button } from "@/components/ui/button";

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
      <div className="p-6">
        <h1 className="text-xl font-semibold mb-2">Training</h1>
        <p className="text-sm text-muted-foreground">Select a project to configure training.</p>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-2xl space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Training</h1>
        {localTraining && (
          <Button onClick={handleSave} disabled={saveConfig.isPending} size="sm">
            {saveConfig.isPending ? "Saving…" : "Save Config"}
          </Button>
        )}
      </div>

      {isLoading && <div className="text-sm text-muted-foreground">Loading config…</div>}
      {error && <div className="text-sm text-destructive">Failed to load config.</div>}

      {localTraining && (
        <TrainingForm config={localTraining} datasetSize={null} onChange={handleChange} />
      )}
    </div>
  );
}
