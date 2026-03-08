import { Outlet } from "react-router-dom";
import { PanelRight } from "lucide-react";
import { Sidebar } from "./sidebar";
import { RightDrawer } from "./right-drawer";
import { BottomPanel } from "./bottom-panel";
import { useAppStore } from "@/stores/app-store";
import { Button } from "@/components/ui/button";

export function AppShell(): React.JSX.Element {
  const { openRightDrawer, isRightDrawerOpen, rightDrawerContent } = useAppStore();

  const handleToggleDrawer = (): void => {
    if (isRightDrawerOpen) {
      useAppStore.getState().closeRightDrawer();
    } else {
      openRightDrawer(rightDrawerContent ?? "run-detail");
    }
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background">
      <Sidebar />
      <div className="flex flex-col flex-1 min-w-0">
        <header className="flex items-center justify-end h-14 px-4 border-b border-border shrink-0">
          <Button
            variant="ghost"
            size="icon"
            onClick={handleToggleDrawer}
            aria-label="Toggle right drawer"
            aria-expanded={isRightDrawerOpen}
          >
            <PanelRight className="h-4 w-4" />
          </Button>
        </header>
        <main className="flex-1 overflow-y-auto min-h-0">
          <Outlet />
        </main>
        <BottomPanel />
      </div>
      <RightDrawer />
    </div>
  );
}
