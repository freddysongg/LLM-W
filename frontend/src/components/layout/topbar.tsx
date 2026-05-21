import * as React from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  Search,
  ChevronDown,
  Bell,
  HelpCircle,
  PanelRight,
  Check,
  Folder,
  ArrowRight,
  Plus,
  BookOpen,
  ExternalLink,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/stores/app-store";
import { useProjects } from "@/hooks/useProjects";
import { useNotifications, useMarkNotificationRead } from "@/hooks/useNotifications";
import { useToast } from "@/hooks/use-toast";
import { getCrumbs } from "@/lib/nav";
import type { Project } from "@/types/project";
import type { Notification } from "@/types/notification";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

const PROJECT_NAME_FALLBACK = "Workbench";

const NOTIFICATION_TYPE_COLOR: Readonly<Record<string, string>> = {
  run_created: "text-ink-2",
  run_started: "text-info",
  run_completed: "text-success",
  run_failed: "text-danger",
  ai_suggestion: "text-iris-4",
};

function notificationColor(type: string): string {
  return NOTIFICATION_TYPE_COLOR[type] ?? "text-ink-3";
}

function formatNotificationTimestamp(iso: string): string {
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) return "";
  return parsed.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

interface CrumbsProps {
  readonly crumbs: readonly string[];
}

function Crumbs({ crumbs }: CrumbsProps): React.JSX.Element {
  const lastIndex = crumbs.length - 1;
  return (
    <div
      className="flex items-center gap-2 font-mono text-[12px] text-ink-3 min-w-0"
      aria-label="Breadcrumb"
    >
      {crumbs.map((crumb, index) => (
        <React.Fragment key={`${crumb}-${index}`}>
          {index > 0 && (
            <span className="opacity-50" aria-hidden="true">
              /
            </span>
          )}
          <span className={cn("truncate", index === lastIndex && "text-ink-1 font-medium")}>
            {crumb}
          </span>
        </React.Fragment>
      ))}
    </div>
  );
}

interface ProjectChipProps {
  readonly projects: readonly Project[];
  readonly activeProject: Project | null;
}

function ProjectChip({ projects, activeProject }: ProjectChipProps): React.JSX.Element {
  const navigate = useNavigate();
  const { toast } = useToast();
  const setActiveProjectId = useAppStore((state) => state.setActiveProjectId);
  const displayName = activeProject?.name ?? PROJECT_NAME_FALLBACK;

  const handleSelectProject = (project: Project): void => {
    setActiveProjectId(project.id);
    toast({ title: `Switched project · ${project.name}` });
  };

  const handleNavigateAll = (): void => {
    navigate("/projects");
  };

  const handleNewProject = (): void => {
    navigate("/projects");
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="inline-flex items-center gap-2 py-1 pl-1.5 pr-2.5 rounded-full border border-hairline bg-surface font-mono text-[12px] text-ink-1 hover:border-hairline-strong hover:bg-surface-2 transition-colors"
        >
          <span
            aria-hidden="true"
            className="w-[18px] h-[18px] rounded-[6px]"
            style={{ background: "linear-gradient(135deg, var(--iris-2), var(--iris-3))" }}
          />
          <span className="truncate max-w-[200px]">{displayName}</span>
          <ChevronDown className="h-3 w-3 opacity-50" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64">
        <DropdownMenuLabel>Switch project</DropdownMenuLabel>
        {projects.length === 0 && (
          <DropdownMenuItem disabled>
            <span className="text-ink-4">No projects yet</span>
          </DropdownMenuItem>
        )}
        {projects.map((project) => {
          const isActive = activeProject?.id === project.id;
          return (
            <DropdownMenuItem key={project.id} onSelect={() => handleSelectProject(project)}>
              <Folder className="h-4 w-4" />
              <span className="flex-1 truncate">{project.name}</span>
              {isActive && <Check className="h-3.5 w-3.5 text-ink-1" />}
            </DropdownMenuItem>
          );
        })}
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={handleNavigateAll}>
          <ArrowRight className="h-4 w-4" />
          <span>All projects…</span>
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={handleNewProject}>
          <Plus className="h-4 w-4" />
          <span>New project</span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function SearchChip(): React.JSX.Element {
  const setCommandPaletteOpen = useAppStore((state) => state.setCommandPaletteOpen);

  return (
    <button
      type="button"
      onClick={() => setCommandPaletteOpen(true)}
      className="hidden md:inline-flex items-center gap-2 py-[5px] pl-2.5 pr-2 rounded-[10px] border border-hairline bg-surface text-ink-3 text-[12px] min-w-[200px] hover:border-hairline-strong transition-colors"
      aria-label="Open command palette"
    >
      <Search className="h-3.5 w-3.5" />
      <span className="flex-1 text-left">Search runs, configs…</span>
      <span className="font-mono text-[10px] py-0.5 px-1.5 border border-hairline rounded bg-surface-2 leading-none">
        ⌘K
      </span>
    </button>
  );
}

function NotificationsMenu(): React.JSX.Element {
  const { data: notifications } = useNotifications();
  const markRead = useMarkNotificationRead();
  const unreadCount = (notifications ?? []).filter(
    (notification: Notification) => notification.readAt === null,
  ).length;

  const handleSelectNotification = (notification: Notification): void => {
    if (notification.readAt === null) {
      markRead.mutate({ id: notification.id });
    }
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label="Notifications"
          className="relative inline-flex items-center justify-center w-8 h-8 rounded-[10px] text-ink-3 hover:bg-surface-2 hover:text-ink-1 transition-colors"
        >
          <Bell className="h-4 w-4" />
          {unreadCount > 0 ? (
            <span
              aria-hidden="true"
              className="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full"
              style={{ background: "var(--danger)" }}
            />
          ) : null}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-80">
        <DropdownMenuLabel>{`Notifications · ${unreadCount} new`}</DropdownMenuLabel>
        {notifications === undefined || notifications.length === 0 ? (
          <div className="px-2 py-3 font-mono text-[11px] text-ink-3">No notifications yet.</div>
        ) : (
          notifications.map((notification: Notification) => {
            const { id, type, title, subtitle, createdAt, readAt } = notification;
            return (
              <DropdownMenuItem
                key={id}
                onSelect={() => handleSelectNotification(notification)}
                className="gap-3 py-2"
              >
                <Bell className={cn("h-3.5 w-3.5 shrink-0", notificationColor(type))} />
                <div className="flex-1 min-w-0">
                  <div
                    className={cn(
                      "text-[12px] truncate",
                      readAt === null ? "text-ink-1" : "text-ink-3",
                    )}
                  >
                    {title}
                  </div>
                  {subtitle !== null ? (
                    <div className="font-mono text-[10px] text-ink-3 truncate">{subtitle}</div>
                  ) : null}
                </div>
                <span className="font-mono text-[10px] text-ink-4 shrink-0">
                  {formatNotificationTimestamp(createdAt)}
                </span>
              </DropdownMenuItem>
            );
          })
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function HelpMenu(): React.JSX.Element {
  const { toast } = useToast();

  const handleOpenDocs = (): void => {
    window.open("https://example.com", "_blank", "noopener,noreferrer");
  };

  const handleShowToast = (title: string): void => {
    toast({ title });
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label="Help"
          className="inline-flex items-center justify-center w-8 h-8 rounded-[10px] text-ink-3 hover:bg-surface-2 hover:text-ink-1 transition-colors"
        >
          <HelpCircle className="h-4 w-4" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuItem onSelect={handleOpenDocs}>
          <BookOpen className="h-4 w-4" />
          <span>Documentation</span>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => handleShowToast("Opened support form")}>
          <ExternalLink className="h-4 w-4" />
          <span>Contact support</span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

interface TopbarProps {
  readonly onToggleRightDrawer: () => void;
  readonly isRightDrawerOpen: boolean;
}

export function Topbar({ onToggleRightDrawer, isRightDrawerOpen }: TopbarProps): React.JSX.Element {
  const { pathname } = useLocation();
  const { data: projectsData } = useProjects();
  const activeProjectId = useAppStore((state) => state.activeProjectId);

  const projects: readonly Project[] = projectsData ?? [];
  const activeProject = projects.find((project) => project.id === activeProjectId) ?? null;
  const projectName = activeProject?.name ?? PROJECT_NAME_FALLBACK;
  const crumbs = getCrumbs({ pathname, projectName });

  return (
    <header
      className="sticky top-0 z-20 flex items-center gap-3.5 h-[54px] px-7 border-b border-hairline bg-surface/80 backdrop-blur-md"
      role="banner"
    >
      <Crumbs crumbs={crumbs} />
      <div className="flex-1" />
      <ProjectChip projects={projects} activeProject={activeProject} />
      <SearchChip />
      <NotificationsMenu />
      <HelpMenu />
      <button
        type="button"
        onClick={onToggleRightDrawer}
        aria-label="Toggle right drawer"
        aria-expanded={isRightDrawerOpen}
        className="inline-flex items-center justify-center w-8 h-8 rounded-[10px] text-ink-3 hover:bg-surface-2 hover:text-ink-1 transition-colors"
      >
        <PanelRight className="h-4 w-4" />
      </button>
    </header>
  );
}
