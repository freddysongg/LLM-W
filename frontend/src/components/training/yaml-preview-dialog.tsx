import * as React from "react";
import { useQueryClient } from "@tanstack/react-query";

import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { CodeBlock } from "@/components/shared/code-block";
import { YamlEditorPane } from "@/components/config/yaml-editor-pane";
import { ConfigVersionsPanel } from "@/components/config/config-versions-panel";
import { fetchConfigYamlByVersion, validateYamlInline } from "@/api/config-versions";
import { CONFIG_VERSIONS_KEY } from "@/hooks/useConfigVersions";
import { useSaveConfig } from "@/hooks/useConfigs";
import { useToast } from "@/hooks/use-toast";
import type { ConfigVersionSummary } from "@/types/config-version";

type DialogMode = "view" | "edit";

type PendingAction =
  | { readonly kind: "close" }
  | { readonly kind: "restore"; readonly version: ConfigVersionSummary };

interface YamlPreviewDialogProps {
  readonly isOpen: boolean;
  readonly projectId: string;
  readonly activeVersionId: string | null;
  readonly yamlContent: string;
  readonly onClose: () => void;
}

export function YamlPreviewDialog({
  isOpen,
  projectId,
  activeVersionId,
  yamlContent,
  onClose,
}: YamlPreviewDialogProps): React.JSX.Element {
  const [mode, setMode] = React.useState<DialogMode>("view");
  const [editorYaml, setEditorYaml] = React.useState<string>(yamlContent);
  const [schemaErrors, setSchemaErrors] = React.useState<ReadonlyArray<string>>([]);
  const [isDirty, setIsDirty] = React.useState<boolean>(false);
  const [pendingAction, setPendingAction] = React.useState<PendingAction | null>(null);
  const [rollbackDetail, setRollbackDetail] = React.useState<string | null>(null);

  const { toast } = useToast();
  const queryClient = useQueryClient();
  const saveMutation = useSaveConfig({ projectId });

  React.useEffect(() => {
    if (isOpen) {
      setMode("view");
      setEditorYaml(yamlContent);
      setSchemaErrors([]);
      setIsDirty(false);
      setRollbackDetail(null);
    }
  }, [isOpen, yamlContent]);

  const loadVersionIntoEditor = React.useCallback(
    async (version: ConfigVersionSummary): Promise<void> => {
      try {
        const loadedYaml = await fetchConfigYamlByVersion({
          projectId,
          versionId: version.id,
        });
        setEditorYaml(loadedYaml);
        setRollbackDetail(`rollback_from_v${version.versionNumber}`);
        setSchemaErrors([]);
        setMode("edit");
      } catch (loadError) {
        toast({
          title: "Failed to load version",
          description: loadError instanceof Error ? loadError.message : "Unknown error",
          variant: "destructive",
        });
      }
    },
    [projectId, toast],
  );

  const handleCloseRequest = (): void => {
    if (mode === "edit" && isDirty) {
      setPendingAction({ kind: "close" });
      return;
    }
    onClose();
  };

  const handleRestoreRequest = (version: ConfigVersionSummary): void => {
    if (mode === "edit" && isDirty) {
      setPendingAction({ kind: "restore", version });
      return;
    }
    void loadVersionIntoEditor(version);
  };

  const handleSave = async (yamlText: string): Promise<void> => {
    setSchemaErrors([]);
    try {
      const validation = await validateYamlInline({
        projectId,
        yamlContent: yamlText,
      });
      if (!validation.isValid) {
        setSchemaErrors(validation.errors);
        return;
      }
    } catch (validationError) {
      toast({
        title: "Validation failed",
        description: validationError instanceof Error ? validationError.message : "Unknown error",
        variant: "destructive",
      });
      return;
    }

    const sourceDetail = rollbackDetail ?? "yaml_paste";

    try {
      await saveMutation.mutateAsync({
        request: {
          projectId,
          yamlContent: yamlText,
          sourceTag: "user",
          sourceDetail,
        },
      });
      await queryClient.invalidateQueries({
        queryKey: CONFIG_VERSIONS_KEY(projectId),
      });
      toast({
        title: "Saved as new version",
        description: sourceDetail,
      });
      setMode("view");
      setRollbackDetail(null);
      setIsDirty(false);
    } catch (saveError) {
      toast({
        title: "Failed to save",
        description: saveError instanceof Error ? saveError.message : "Unknown error",
        variant: "destructive",
      });
    }
  };

  const handleViewClick = (): void => {
    if (mode === "edit" && isDirty) {
      setPendingAction({ kind: "close" });
      return;
    }
    setMode("view");
    setRollbackDetail(null);
  };

  const handlePendingConfirm = (): void => {
    const action = pendingAction;
    setPendingAction(null);
    if (action === null) return;
    if (action.kind === "close") {
      onClose();
      return;
    }
    void loadVersionIntoEditor(action.version);
  };

  return (
    <>
      <Dialog
        open={isOpen}
        onOpenChange={(open) => {
          if (!open) handleCloseRequest();
        }}
      >
        <DialogContent className="max-w-[720px]">
          <DialogHeader>
            <DialogTitle>YAML config</DialogTitle>
            <div className="flex gap-1">
              <Button
                variant={mode === "view" ? "primary" : "outline"}
                size="sm"
                onClick={handleViewClick}
              >
                View
              </Button>
              <Button
                variant={mode === "edit" ? "primary" : "outline"}
                size="sm"
                onClick={() => setMode("edit")}
              >
                Edit
              </Button>
            </div>
          </DialogHeader>

          <div className="flex flex-col gap-3 overflow-y-auto px-6 py-5">
            {mode === "view" ? (
              <div className="max-h-[360px] overflow-auto">
                <CodeBlock code={yamlContent} language="yaml" />
              </div>
            ) : (
              <YamlEditorPane
                initialYaml={editorYaml}
                isSaving={saveMutation.isPending}
                schemaErrors={schemaErrors}
                onDirtyChange={setIsDirty}
                onSave={(text) => void handleSave(text)}
                onCancel={handleCloseRequest}
              />
            )}

            <ConfigVersionsPanel
              projectId={projectId}
              activeVersionId={activeVersionId}
              onRestore={handleRestoreRequest}
            />
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={handleCloseRequest}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog
        open={pendingAction !== null}
        onOpenChange={(open) => {
          if (!open) setPendingAction(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Discard unsaved edits?</AlertDialogTitle>
            <AlertDialogDescription>Your current edits will be lost.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep editing</AlertDialogCancel>
            <AlertDialogAction onClick={handlePendingConfirm}>Discard</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
