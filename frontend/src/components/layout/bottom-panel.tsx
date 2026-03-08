import { Terminal, ChevronDown, ChevronUp } from "lucide-react";
import { useAppStore } from "@/stores/app-store";
import { Button } from "@/components/ui/button";

const MIN_HEIGHT = 100;
const MAX_HEIGHT = 400;

export function BottomPanel(): React.JSX.Element {
  const { isBottomPanelVisible, bottomPanelHeight, toggleBottomPanel, setBottomPanelHeight } =
    useAppStore();

  const handleResizeStart = (e: React.MouseEvent<HTMLDivElement>): void => {
    const startY = e.clientY;
    const startHeight = bottomPanelHeight;

    const onMouseMove = (moveEvent: MouseEvent): void => {
      const delta = startY - moveEvent.clientY;
      const newHeight = Math.max(MIN_HEIGHT, Math.min(MAX_HEIGHT, startHeight + delta));
      setBottomPanelHeight(newHeight);
    };

    const onMouseUp = (): void => {
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
    };

    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
  };

  return (
    <div className="border-t border-border bg-background shrink-0">
      {isBottomPanelVisible && (
        <div
          className="w-full h-1 cursor-row-resize bg-transparent hover:bg-border/60 transition-colors"
          onMouseDown={handleResizeStart}
          role="separator"
          aria-orientation="horizontal"
          aria-label="Resize log panel"
        />
      )}
      <div className="flex items-center h-9 px-4 gap-2">
        <Terminal className="h-3.5 w-3.5 text-muted-foreground" />
        <span className="text-xs font-medium text-muted-foreground flex-1">Logs</span>
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6"
          onClick={toggleBottomPanel}
          aria-label={isBottomPanelVisible ? "Collapse log panel" : "Expand log panel"}
        >
          {isBottomPanelVisible ? (
            <ChevronDown className="h-3.5 w-3.5" />
          ) : (
            <ChevronUp className="h-3.5 w-3.5" />
          )}
        </Button>
      </div>
      {isBottomPanelVisible && (
        <div
          className="overflow-y-auto border-t border-border"
          style={{ height: bottomPanelHeight }}
        >
          <div className="flex items-center justify-center h-full text-sm text-muted-foreground">
            Log output will appear here
          </div>
        </div>
      )}
    </div>
  );
}
