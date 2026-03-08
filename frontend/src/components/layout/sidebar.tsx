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
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/stores/app-store";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

interface NavItem {
  readonly label: string;
  readonly path: string;
  readonly icon: React.ComponentType<{ className?: string }>;
}

const NAV_ITEMS: ReadonlyArray<NavItem> = [
  { label: "Dashboard", path: "/", icon: LayoutDashboard },
  { label: "Projects", path: "/projects", icon: FolderKanban },
  { label: "Models", path: "/models", icon: Brain },
  { label: "Datasets", path: "/datasets", icon: Database },
  { label: "Training", path: "/training", icon: Dumbbell },
  { label: "Adapters & Optimization", path: "/adapters", icon: Puzzle },
  { label: "Weights & Architecture", path: "/weights", icon: Layers },
  { label: "Runs", path: "/runs", icon: Play },
  { label: "Compare", path: "/compare", icon: GitCompareArrows },
  { label: "AI Suggestions", path: "/suggestions", icon: Sparkles },
  { label: "Artifacts", path: "/artifacts", icon: Archive },
  { label: "Settings", path: "/settings", icon: Settings },
];

export function Sidebar(): React.JSX.Element {
  const { isSidebarCollapsed, toggleSidebar } = useAppStore();

  return (
    <TooltipProvider delayDuration={300}>
      <aside
        className={cn(
          "flex flex-col h-full border-r border-border bg-sidebar transition-all duration-150 shrink-0",
          isSidebarCollapsed ? "w-[60px]" : "w-[240px]",
        )}
      >
        <div className="flex items-center h-14 px-3 border-b border-border shrink-0">
          {!isSidebarCollapsed && (
            <span className="text-sm font-semibold tracking-tight truncate flex-1 text-sidebar-foreground">
              Workbench
            </span>
          )}
        </div>
        <nav className="flex-1 overflow-y-auto py-2 px-2" aria-label="Main navigation">
          <ul className="space-y-0.5">
            {NAV_ITEMS.map(({ label, path, icon: Icon }) => (
              <li key={path}>
                {isSidebarCollapsed ? (
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <NavLink
                        to={path}
                        end={path === "/"}
                        className={({ isActive }) =>
                          cn(
                            "flex items-center justify-center h-9 w-9 mx-auto rounded-md text-sidebar-foreground/60 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground transition-colors",
                            isActive &&
                              "bg-sidebar-accent text-sidebar-accent-foreground font-medium",
                          )
                        }
                        aria-label={label}
                      >
                        <Icon className="h-4 w-4" />
                      </NavLink>
                    </TooltipTrigger>
                    <TooltipContent side="right">{label}</TooltipContent>
                  </Tooltip>
                ) : (
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
                )}
              </li>
            ))}
          </ul>
        </nav>
        <div className="border-t border-border p-2 shrink-0">
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
