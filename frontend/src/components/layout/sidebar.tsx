import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  FolderKanban,
  Brain,
  Database,
  Dumbbell,
  Puzzle,
  Layers,
  Play,
  GitCompareArrows,
  Sparkles,
  Archive,
  Settings,
  PanelLeftClose,
  PanelLeftOpen,
  ChevronRight,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/stores/app-store";
import type { NavGroupKey } from "@/stores/app-store";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";

interface NavItem {
  readonly label: string;
  readonly path: string;
  readonly icon: React.ComponentType<{ className?: string }>;
}

interface NavGroup {
  readonly key: NavGroupKey;
  readonly label: string;
  readonly items: ReadonlyArray<NavItem>;
}

const NAV_GROUPS: ReadonlyArray<NavGroup> = [
  {
    key: "overview",
    label: "Overview",
    items: [
      { label: "Dashboard", path: "/", icon: LayoutDashboard },
      { label: "Projects", path: "/projects", icon: FolderKanban },
    ],
  },
  {
    key: "modelData",
    label: "Model & Data",
    items: [
      { label: "Models", path: "/models", icon: Brain },
      { label: "Datasets", path: "/datasets", icon: Database },
    ],
  },
  {
    key: "training",
    label: "Training",
    items: [
      { label: "Training", path: "/training", icon: Dumbbell },
      { label: "Adapters & Optimization", path: "/adapters", icon: Puzzle },
      { label: "Weights & Architecture", path: "/weights", icon: Layers },
    ],
  },
  {
    key: "execution",
    label: "Execution",
    items: [
      { label: "Runs", path: "/runs", icon: Play },
      { label: "Compare", path: "/compare", icon: GitCompareArrows },
    ],
  },
  {
    key: "intelligence",
    label: "Intelligence",
    items: [
      { label: "AI Suggestions", path: "/suggestions", icon: Sparkles },
      { label: "Artifacts", path: "/artifacts", icon: Archive },
    ],
  },
];

const SETTINGS_ITEM: NavItem = { label: "Settings", path: "/settings", icon: Settings };

interface CollapsedNavItemProps {
  readonly item: NavItem;
}

function CollapsedNavItem({ item }: CollapsedNavItemProps): React.JSX.Element {
  const { label, path, icon: Icon } = item;
  return (
    <li key={path}>
      <Tooltip>
        <TooltipTrigger asChild>
          <NavLink
            to={path}
            end={path === "/"}
            className={({ isActive }) =>
              cn(
                "flex items-center justify-center h-9 w-9 mx-auto rounded-md text-sidebar-foreground/60 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground transition-colors",
                isActive && "bg-sidebar-accent text-sidebar-accent-foreground font-medium",
              )
            }
            aria-label={label}
          >
            <Icon className="h-4 w-4" />
          </NavLink>
        </TooltipTrigger>
        <TooltipContent side="right">{label}</TooltipContent>
      </Tooltip>
    </li>
  );
}

interface ExpandedNavItemProps {
  readonly item: NavItem;
}

function ExpandedNavItem({ item }: ExpandedNavItemProps): React.JSX.Element {
  const { label, path, icon: Icon } = item;
  return (
    <li key={path}>
      <NavLink
        to={path}
        end={path === "/"}
        className={({ isActive }) =>
          cn(
            "flex items-center gap-2.5 h-9 px-2.5 rounded-md text-sm text-sidebar-foreground/60 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground transition-colors",
            isActive && "bg-sidebar-accent text-sidebar-accent-foreground font-medium",
          )
        }
      >
        <Icon className="h-4 w-4 shrink-0" />
        <span className="truncate">{label}</span>
      </NavLink>
    </li>
  );
}

export function Sidebar(): React.JSX.Element {
  const { isSidebarCollapsed, toggleSidebar, navGroupExpanded, toggleNavGroup } = useAppStore();

  return (
    <TooltipProvider delayDuration={300}>
      <aside
        className={cn(
          "flex flex-col h-full border-r border-border bg-sidebar transition-all duration-150 shrink-0",
          isSidebarCollapsed ? "w-[60px]" : "w-[240px]",
        )}
      >
        <div className="flex items-center h-14 px-3 border-b border-border shrink-0">
          <img
            src="/workbench-transparent.png"
            alt="Workbench logo"
            className="h-6 w-6 shrink-0 dark:invert"
          />
          {!isSidebarCollapsed && (
            <span className="text-sm font-semibold tracking-tight truncate flex-1 text-sidebar-foreground ml-2">
              Workbench
            </span>
          )}
        </div>
        <nav className="flex-1 overflow-y-auto py-2 px-2" aria-label="Main navigation">
          {isSidebarCollapsed ? (
            <ul className="space-y-0.5">
              {NAV_GROUPS.flatMap(({ items }) => items).map((item) => (
                <CollapsedNavItem key={item.path} item={item} />
              ))}
              <CollapsedNavItem item={SETTINGS_ITEM} />
            </ul>
          ) : (
            <div className="space-y-1">
              {NAV_GROUPS.map(({ key, label, items }) => (
                <Collapsible
                  key={key}
                  open={navGroupExpanded[key]}
                  onOpenChange={() => toggleNavGroup(key)}
                >
                  <CollapsibleTrigger asChild>
                    <button
                      className="flex items-center w-full px-2.5 py-1 rounded-md text-xs font-medium text-sidebar-foreground/40 hover:text-sidebar-foreground/60 transition-colors"
                      aria-label={`Toggle ${label} group`}
                    >
                      <ChevronRight
                        className={cn(
                          "h-3 w-3 mr-1.5 shrink-0 transition-transform duration-150",
                          navGroupExpanded[key] && "rotate-90",
                        )}
                      />
                      <span className="uppercase tracking-wider">{label}</span>
                    </button>
                  </CollapsibleTrigger>
                  <CollapsibleContent className="data-[state=open]:animate-none">
                    <ul className="space-y-0.5 mt-0.5">
                      {items.map((item) => (
                        <ExpandedNavItem key={item.path} item={item} />
                      ))}
                    </ul>
                  </CollapsibleContent>
                </Collapsible>
              ))}
              <div className="mt-1 pt-1 border-t border-border/50">
                <ul>
                  <ExpandedNavItem item={SETTINGS_ITEM} />
                </ul>
              </div>
            </div>
          )}
        </nav>
        <div className="border-t border-border shrink-0 flex items-center justify-center h-9 px-2">
          <Button
            variant="ghost"
            size="icon"
            onClick={toggleSidebar}
            className={cn(
              "h-9 w-9 text-sidebar-foreground/60",
              isSidebarCollapsed ? "mx-auto" : "ml-auto",
            )}
            aria-label={isSidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {isSidebarCollapsed ? (
              <PanelLeftOpen className="h-4 w-4" />
            ) : (
              <PanelLeftClose className="h-4 w-4" />
            )}
          </Button>
        </div>
      </aside>
    </TooltipProvider>
  );
}
