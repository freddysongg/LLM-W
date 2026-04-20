import * as React from "react";
import { Outlet, useLocation } from "react-router-dom";
import { Sidebar } from "./sidebar";
import { Topbar } from "./topbar";
import { RightDrawer } from "./right-drawer";
import { BottomPanel } from "./bottom-panel";
import { CommandPalette } from "./command-palette";
import { TweaksPanel } from "./tweaks-panel";
import { useAppStore } from "@/stores/app-store";
import { useGlobalShortcuts } from "@/hooks/use-global-shortcuts";
import { getRouteSlug } from "@/lib/nav";

export function AppShell(): React.JSX.Element {
  const { pathname } = useLocation();
  const isRightDrawerOpen = useAppStore((state) => state.isRightDrawerOpen);
  const rightDrawerContent = useAppStore((state) => state.rightDrawerContent);
  const openRightDrawer = useAppStore((state) => state.openRightDrawer);
  const closeRightDrawer = useAppStore((state) => state.closeRightDrawer);
  const toggleSidebar = useAppStore((state) => state.toggleSidebar);
  const setCommandPaletteOpen = useAppStore((state) => state.setCommandPaletteOpen);

  const handleToggleRightDrawer = React.useCallback((): void => {
    if (isRightDrawerOpen) {
      closeRightDrawer();
    } else {
      openRightDrawer({ content: rightDrawerContent ?? "run-detail" });
    }
  }, [closeRightDrawer, isRightDrawerOpen, openRightDrawer, rightDrawerContent]);

  const handleOpenCommandPalette = React.useCallback((): void => {
    setCommandPaletteOpen(true);
  }, [setCommandPaletteOpen]);

  useGlobalShortcuts({
    onOpenCommandPalette: handleOpenCommandPalette,
    onToggleSidebar: toggleSidebar,
  });

  const pageSlug = getRouteSlug(pathname);

  return (
    <div className="flex h-screen w-screen overflow-hidden" style={{ background: "var(--canvas)" }}>
      <Sidebar />
      <div className="flex flex-col flex-1 min-w-0" data-page={pageSlug}>
        <Topbar
          onToggleRightDrawer={handleToggleRightDrawer}
          isRightDrawerOpen={isRightDrawerOpen}
        />
        <main className="flex-1 overflow-y-auto min-h-0">
          <div key={pathname} className="page-fade">
            <Outlet />
          </div>
        </main>
        <BottomPanel />
      </div>
      <RightDrawer />
      <CommandPalette />
      <TweaksPanel />
    </div>
  );
}
