import { create } from "zustand";

export type DrawerContent =
  | "ai-suggestions"
  | "layer-detail"
  | "run-detail"
  | "project-detail"
  | null;

interface AppState {
  readonly activeProjectId: string | null;
  readonly isSidebarCollapsed: boolean;
  readonly isRightDrawerOpen: boolean;
  readonly rightDrawerContent: DrawerContent;
  readonly isBottomPanelVisible: boolean;
  readonly bottomPanelHeight: number;
}

interface AppActions {
  setActiveProjectId: (projectId: string | null) => void;
  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  openRightDrawer: (content: Exclude<DrawerContent, null>) => void;
  closeRightDrawer: () => void;
  toggleBottomPanel: () => void;
  setBottomPanelHeight: (height: number) => void;
}

type AppStore = AppState & AppActions;

export const useAppStore = create<AppStore>((set) => ({
  activeProjectId: null,
  isSidebarCollapsed: false,
  isRightDrawerOpen: false,
  rightDrawerContent: null,
  isBottomPanelVisible: true,
  bottomPanelHeight: 200,

  setActiveProjectId: (projectId) => set({ activeProjectId: projectId }),
  toggleSidebar: () => set((state) => ({ isSidebarCollapsed: !state.isSidebarCollapsed })),
  setSidebarCollapsed: (collapsed) => set({ isSidebarCollapsed: collapsed }),
  openRightDrawer: (content) => set({ isRightDrawerOpen: true, rightDrawerContent: content }),
  closeRightDrawer: () => set({ isRightDrawerOpen: false, rightDrawerContent: null }),
  toggleBottomPanel: () => set((state) => ({ isBottomPanelVisible: !state.isBottomPanelVisible })),
  setBottomPanelHeight: (height) => set({ bottomPanelHeight: height }),
}));
