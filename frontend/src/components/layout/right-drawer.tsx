import { X } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/stores/app-store";
import { Button } from "@/components/ui/button";

const DRAWER_LABELS: Record<string, string> = {
  "ai-suggestions": "AI Suggestions",
  "layer-detail": "Layer Detail",
  "run-detail": "Run Detail",
  "project-detail": "Project Detail",
};

export function RightDrawer(): React.JSX.Element {
  const { isRightDrawerOpen, rightDrawerContent, closeRightDrawer } = useAppStore();

  const label =
    rightDrawerContent !== null ? (DRAWER_LABELS[rightDrawerContent] ?? rightDrawerContent) : "";

  return (
    <aside
      className={cn(
        "flex flex-col h-full border-l border-border bg-background transition-all duration-150 shrink-0 overflow-hidden",
        isRightDrawerOpen ? "w-80" : "w-0",
      )}
      aria-hidden={!isRightDrawerOpen}
    >
      {isRightDrawerOpen && (
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
            <p className="text-sm text-muted-foreground">Coming soon</p>
          </div>
        </>
      )}
    </aside>
  );
}
