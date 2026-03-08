import { X } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/stores/app-store";
import { Button } from "@/components/ui/button";
import { RunDetailPanel } from "./drawer-panels/run-detail-panel";
import { LayerDetailPanel } from "./drawer-panels/layer-detail-panel";
import { ProjectDetailPanel } from "./drawer-panels/project-detail-panel";
import { AiSuggestionDetailPanel } from "./drawer-panels/ai-suggestion-detail-panel";
import type { DrawerContent } from "@/stores/app-store";

const DRAWER_LABELS: Record<Exclude<DrawerContent, null>, string> = {
  "ai-suggestions": "AI Suggestions",
  "layer-detail": "Layer Detail",
  "run-detail": "Run Detail",
  "project-detail": "Project Detail",
};

interface DrawerBodyProps {
  readonly content: Exclude<DrawerContent, null>;
  readonly projectId: string | null;
  readonly runId: string | null;
  readonly layerName: string | null;
  readonly suggestionId: string | null;
}

function DrawerBody({
  content,
  projectId,
  runId,
  layerName,
  suggestionId,
}: DrawerBodyProps): React.JSX.Element {
  if (!projectId) {
    return <p className="text-sm text-muted-foreground">No context selected.</p>;
  }

  switch (content) {
    case "run-detail":
      if (!runId) return <p className="text-sm text-muted-foreground">No run selected.</p>;
      return <RunDetailPanel projectId={projectId} runId={runId} />;
    case "layer-detail":
      if (!layerName) return <p className="text-sm text-muted-foreground">No layer selected.</p>;
      return <LayerDetailPanel projectId={projectId} layerName={layerName} />;
    case "project-detail":
      return <ProjectDetailPanel projectId={projectId} />;
    case "ai-suggestions":
      if (!suggestionId)
        return <p className="text-sm text-muted-foreground">No suggestion selected.</p>;
      return <AiSuggestionDetailPanel projectId={projectId} suggestionId={suggestionId} />;
    default: {
      const _exhaustive: never = content;
      return _exhaustive;
    }
  }
}

export function RightDrawer(): React.JSX.Element {
  const {
    isRightDrawerOpen,
    rightDrawerContent,
    closeRightDrawer,
    drawerProjectId,
    drawerRunId,
    drawerLayerName,
    drawerSuggestionId,
  } = useAppStore();

  const label = rightDrawerContent !== null ? DRAWER_LABELS[rightDrawerContent] : "";

  return (
    <aside
      className={cn(
        "flex flex-col h-full border-l border-border bg-background transition-all duration-150 shrink-0 overflow-hidden",
        isRightDrawerOpen ? "w-80" : "w-0",
      )}
      aria-hidden={!isRightDrawerOpen}
    >
      {isRightDrawerOpen && rightDrawerContent !== null && (
        <>
          <div className="flex items-center justify-between h-14 px-4 border-b border-border shrink-0">
            <span className="text-sm font-medium">{label}</span>
            <Button
              variant="ghost"
              size="icon"
              onClick={closeRightDrawer}
              aria-label="Close drawer"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
          <div className="flex-1 overflow-y-auto p-4">
            <DrawerBody
              content={rightDrawerContent}
              projectId={drawerProjectId}
              runId={drawerRunId}
              layerName={drawerLayerName}
              suggestionId={drawerSuggestionId}
            />
          </div>
        </>
      )}
    </aside>
  );
}
