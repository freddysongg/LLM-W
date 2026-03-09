import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { ModelSource } from "@/types/model";
import type { DatasetSource, DatasetFormat } from "@/types/config";

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

export interface ModelFormState {
  readonly source: ModelSource;
  readonly modelId: string;
}

export interface DatasetFormState {
  readonly source: DatasetSource;
  readonly datasetId: string;
  readonly format: DatasetFormat;
  readonly formatMapping: Record<string, string>;
  readonly filterExpression: string;
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
  readonly modelForm: ModelFormState;
  readonly datasetForm: DatasetFormState;
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
  setModelForm: (updates: Partial<ModelFormState>) => void;
  setDatasetForm: (updates: Partial<DatasetFormState>) => void;
}

type AppStore = AppState & AppActions;

const DEFAULT_NAV_GROUP_EXPANDED: NavGroupExpandedState = {
  overview: true,
  modelData: true,
  training: true,
  execution: true,
  intelligence: true,
};

const DEFAULT_MODEL_FORM: ModelFormState = {
  source: "huggingface",
  modelId: "",
};

const DEFAULT_DATASET_FORM: DatasetFormState = {
  source: "huggingface",
  datasetId: "",
  format: "default",
  formatMapping: {},
  filterExpression: "",
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
      isBottomPanelVisible: false,
      bottomPanelHeight: 200,
      navGroupExpanded: DEFAULT_NAV_GROUP_EXPANDED,
      modelForm: DEFAULT_MODEL_FORM,
      datasetForm: DEFAULT_DATASET_FORM,

      setActiveProjectId: (projectId) => set({ activeProjectId: projectId }),
      toggleSidebar: () => set((state) => ({ isSidebarCollapsed: !state.isSidebarCollapsed })),
      setSidebarCollapsed: (collapsed) => set({ isSidebarCollapsed: collapsed }),
      openRightDrawer: ({
        content,
        projectId = null,
        runId = null,
        layerName = null,
        suggestionId = null,
      }) =>
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
      setModelForm: (updates) =>
        set((state) => ({ modelForm: { ...state.modelForm, ...updates } })),
      setDatasetForm: (updates) =>
        set((state) => ({ datasetForm: { ...state.datasetForm, ...updates } })),
    }),
    {
      name: "app-store",
      partialize: (state) => ({
        activeProjectId: state.activeProjectId,
        navGroupExpanded: state.navGroupExpanded,
        isSidebarCollapsed: state.isSidebarCollapsed,
        modelForm: state.modelForm,
        datasetForm: state.datasetForm,
      }),
    },
  ),
);
