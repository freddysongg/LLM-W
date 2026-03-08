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
  readonly drawerRunId: string | null;
  readonly drawerLayerName: string | null;
  readonly drawerProjectId: string | null;
  readonly drawerSuggestionId: string | null;
}

interface AppActions {
  setActiveProjectId: (projectId: string | null) => void;
  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  openRightDrawer: (content: Exclude<DrawerContent, null>) => void;
  closeRightDrawer: () => void;
  toggleBottomPanel: () => void;
  setBottomPanelHeight: (height: number) => void;
  openRunDetail: (params: { projectId: string; runId: string }) => void;
  openLayerDetail: (params: { projectId: string; layerName: string }) => void;
  openProjectDetail: (params: { projectId: string }) => void;
  openSuggestionDetail: (params: { projectId: string; suggestionId: string }) => void;
}

type AppStore = AppState & AppActions;

export const useAppStore = create<AppStore>((set) => ({
  activeProjectId: null,
  isSidebarCollapsed: false,
  isRightDrawerOpen: false,
  rightDrawerContent: null,
  isBottomPanelVisible: true,
  bottomPanelHeight: 200,
  drawerRunId: null,
  drawerLayerName: null,
  drawerProjectId: null,
  drawerSuggestionId: null,

  setActiveProjectId: (projectId) => set({ activeProjectId: projectId }),
  toggleSidebar: () => set((state) => ({ isSidebarCollapsed: !state.isSidebarCollapsed })),
  setSidebarCollapsed: (collapsed) => set({ isSidebarCollapsed: collapsed }),
  openRightDrawer: (content) => set({ isRightDrawerOpen: true, rightDrawerContent: content }),
  closeRightDrawer: () => set({ isRightDrawerOpen: false, rightDrawerContent: null }),
  toggleBottomPanel: () => set((state) => ({ isBottomPanelVisible: !state.isBottomPanelVisible })),
  setBottomPanelHeight: (height) => set({ bottomPanelHeight: height }),
  openRunDetail: ({ projectId, runId }) =>
    set({
      isRightDrawerOpen: true,
      rightDrawerContent: "run-detail",
      drawerProjectId: projectId,
      drawerRunId: runId,
    }),
  openLayerDetail: ({ projectId, layerName }) =>
    set({
      isRightDrawerOpen: true,
      rightDrawerContent: "layer-detail",
      drawerProjectId: projectId,
      drawerLayerName: layerName,
    }),
  openProjectDetail: ({ projectId }) =>
    set({
      isRightDrawerOpen: true,
      rightDrawerContent: "project-detail",
      drawerProjectId: projectId,
    }),
  openSuggestionDetail: ({ projectId, suggestionId }) =>
    set({
      isRightDrawerOpen: true,
      rightDrawerContent: "ai-suggestions",
      drawerProjectId: projectId,
      drawerSuggestionId: suggestionId,
    }),
}));
