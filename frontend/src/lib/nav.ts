import {
  LayoutGrid,
  Folder,
  Brain,
  Database,
  Dumbbell,
  Puzzle,
  Layers,
  Play,
  ArrowLeftRight,
  ClipboardCheck,
  Sparkles,
  Archive,
  Mic,
  Settings,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

export type NavIcon =
  | "layout"
  | "folder"
  | "brain"
  | "db"
  | "dumbbell"
  | "puzzle"
  | "layers"
  | "play"
  | "compare"
  | "clipboard"
  | "sparkle"
  | "archive"
  | "mic"
  | "cog";

export interface NavItem {
  readonly label: string;
  readonly path: string;
  readonly icon: NavIcon;
  readonly badge?: string;
}

export interface NavGroup {
  readonly key: string;
  readonly label: string;
  readonly items: readonly NavItem[];
}

export const NAV_ICON_COMPONENTS: Record<NavIcon, LucideIcon> = {
  layout: LayoutGrid,
  folder: Folder,
  brain: Brain,
  db: Database,
  dumbbell: Dumbbell,
  puzzle: Puzzle,
  layers: Layers,
  play: Play,
  compare: ArrowLeftRight,
  clipboard: ClipboardCheck,
  sparkle: Sparkles,
  archive: Archive,
  mic: Mic,
  cog: Settings,
};

export const NAV_GROUPS: readonly NavGroup[] = [
  {
    key: "overview",
    label: "Overview",
    items: [
      { label: "Dashboard", path: "/", icon: "layout" },
      { label: "Projects", path: "/projects", icon: "folder" },
    ],
  },
  {
    key: "modelData",
    label: "Model & Data",
    items: [
      { label: "Models", path: "/models", icon: "brain" },
      { label: "Datasets", path: "/datasets", icon: "db" },
    ],
  },
  {
    key: "training",
    label: "Training",
    items: [
      { label: "Training", path: "/training", icon: "dumbbell" },
      { label: "Adapters & Optimization", path: "/adapters", icon: "puzzle" },
      { label: "Weights & Architecture", path: "/weights", icon: "layers" },
    ],
  },
  {
    key: "execution",
    label: "Execution",
    items: [
      { label: "Runs", path: "/runs", icon: "play", badge: "LIVE" },
      { label: "Compare", path: "/compare", icon: "compare" },
      { label: "Evaluation", path: "/eval", icon: "clipboard" },
    ],
  },
  {
    key: "intelligence",
    label: "Intelligence",
    items: [
      { label: "AI Suggestions", path: "/suggestions", icon: "sparkle" },
      { label: "Artifacts", path: "/artifacts", icon: "archive" },
      { label: "Voice demo", path: "/voice-demo", icon: "mic" },
    ],
  },
];

export const SETTINGS_NAV_ITEM: NavItem = {
  label: "Settings",
  path: "/settings",
  icon: "cog",
};

const CRUMB_LEAF_BY_PATH: Record<string, string> = {
  "/": "Dashboard",
  "/projects": "Projects",
  "/models": "Models",
  "/datasets": "Datasets",
  "/training": "Training",
  "/adapters": "Adapters & Optimization",
  "/weights": "Weights & Architecture",
  "/runs": "Runs",
  "/compare": "Compare",
  "/eval": "Evaluation",
  "/suggestions": "AI Suggestions",
  "/artifacts": "Artifacts",
  "/voice-demo": "Voice demo",
  "/settings": "Settings",
};

const PROJECTS_ROOT_LABEL = "Workspace";

export interface GetCrumbsParams {
  readonly pathname: string;
  readonly projectName: string;
}

export function getCrumbs({ pathname, projectName }: GetCrumbsParams): readonly string[] {
  const leaf = CRUMB_LEAF_BY_PATH[pathname];
  if (!leaf) return [];
  const root = pathname === "/projects" ? PROJECTS_ROOT_LABEL : projectName;
  return [root, leaf];
}

export function getRouteSlug(pathname: string): string {
  if (pathname === "/") return "dashboard";
  return pathname.replace(/^\//, "").replace(/\//g, "-");
}
