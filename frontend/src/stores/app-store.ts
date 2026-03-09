import { create } from "zustand";
import { persist } from "zustand/middleware";

export type DrawerContent =
  | "ai-suggestions"
  | "layer-detail"
  | "run-detail"
  | "project-detail"
  | null;

export type NavGroupKey = "overview" | "modelData" | "training" | "execution" | "intelligence";

type NavGroupExpandedState = Record<NavGroupKey, boolean>;

interface DrawerContext {
  readonly content: Exclude<DrawerContent, null>;
  readonly projectId?: string | null;
  readonly runId?: string | null;
  readonly layerName?: string | null;
  readonly suggestionId?: string | null;
}

interface AppState {
  readonly activeProjectId: string | null;
  readonly isSidebarCollapsed: boolean;
  readonly isRightDrawerOpen: boolean;
  readonly rightDrawerContent: DrawerContent;
  readonly drawerProjectId: string | null;
  readonly drawerRunId: string | null;
  readonly drawerLayerName: string | null;
  readonly drawerSuggestionId: string | null;
  readonly isBottomPanelVisible: boolean;
  readonly bottomPanelHeight: number;
  readonly navGroupExpanded: NavGroupExpandedState;
}

interface AppActions {
  setActiveProjectId: (projectId: string | null) => void;
  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  openRightDrawer: (context: DrawerContext) => void;
  closeRightDrawer: () => void;
  toggleBottomPanel: () => void;
  setBottomPanelHeight: (height: number) => void;
  toggleNavGroup: (group: NavGroupKey) => void;
}

type AppStore = AppState & AppActions;

const DEFAULT_NAV_GROUP_EXPANDED: NavGroupExpandedState = {
  overview: true,
  modelData: true,
  training: true,
  execution: true,
  intelligence: true,
};

export const useAppStore = create<AppStore>()(
  persist(
    (set) => ({
      activeProjectId: null,
      isSidebarCollapsed: false,
      isRightDrawerOpen: false,
      rightDrawerContent: null,
      drawerProjectId: null,
      drawerRunId: null,
      drawerLayerName: null,
      drawerSuggestionId: null,
      isBottomPanelVisible: true,
      bottomPanelHeight: 200,
      navGroupExpanded: DEFAULT_NAV_GROUP_EXPANDED,

      setActiveProjectId: (projectId) => set({ activeProjectId: projectId }),
      toggleSidebar: () => set((state) => ({ isSidebarCollapsed: !state.isSidebarCollapsed })),
      setSidebarCollapsed: (collapsed) => set({ isSidebarCollapsed: collapsed }),
      openRightDrawer: ({ content, projectId = null, runId = null, layerName = null, suggestionId = null }) =>
        set({
          isRightDrawerOpen: true,
          rightDrawerContent: content,
          drawerProjectId: projectId,
          drawerRunId: runId,
          drawerLayerName: layerName,
          drawerSuggestionId: suggestionId,
        }),
      closeRightDrawer: () =>
        set({
          isRightDrawerOpen: false,
          rightDrawerContent: null,
          drawerProjectId: null,
          drawerRunId: null,
          drawerLayerName: null,
          drawerSuggestionId: null,
        }),
      toggleBottomPanel: () =>
        set((state) => ({ isBottomPanelVisible: !state.isBottomPanelVisible })),
      setBottomPanelHeight: (height) => set({ bottomPanelHeight: height }),
      toggleNavGroup: (group) =>
        set((state) => ({
          navGroupExpanded: {
            ...state.navGroupExpanded,
            [group]: !state.navGroupExpanded[group],
          },
        })),
    }),
    {
      name: "app-store",
      partialize: (state) => ({
        navGroupExpanded: state.navGroupExpanded,
        isSidebarCollapsed: state.isSidebarCollapsed,
      }),
    },
  ),
);
