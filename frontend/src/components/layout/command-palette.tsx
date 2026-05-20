import * as React from "react";
import { useNavigate } from "react-router-dom";
import { Command as CommandPrimitive } from "cmdk";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import {
  Search,
  ArrowRight,
  Zap,
  Settings as SettingsIcon,
  SlidersHorizontal,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/stores/app-store";
import { useToast } from "@/hooks/use-toast";
import { useRuns } from "@/hooks/useRuns";
import { NAV_GROUPS, SETTINGS_NAV_ITEM } from "@/lib/nav";
import { STORAGE_KEYS, THEME_VALUES, type Theme } from "@/lib/theme-init";
import { Kbd } from "@/components/ui/kbd";
import type { Run } from "@/types/run";

type CommandHint = "nav" | "action" | "pref";

interface CommandDefinition {
  readonly id: string;
  readonly label: string;
  readonly hint: CommandHint;
  readonly icon: LucideIcon;
  readonly run: () => void;
}

interface NavigateWithToastParams {
  readonly path: string;
  readonly toastTitle: string;
}

type ToastFn = ReturnType<typeof useToast>["toast"];

interface BuildCommandsParams {
  readonly navigate: ReturnType<typeof useNavigate>;
  readonly toast: ToastFn;
  readonly openTweaks: () => void;
  readonly activeRunId: string | null;
}

const HINT_ICON_BY_KIND: Record<CommandHint, LucideIcon> = {
  nav: ArrowRight,
  action: Zap,
  pref: SettingsIcon,
};

const HINT_GROUP_LABEL: Record<CommandHint, string> = {
  nav: "Navigation",
  action: "Actions",
  pref: "Preferences",
};

const HINT_ORDER: readonly CommandHint[] = ["nav", "action", "pref"];

const ACTIVE_RUN_STATUSES: ReadonlySet<Run["status"]> = new Set<Run["status"]>([
  "running",
  "pending",
  "fallback_pending",
]);

function findActiveRunId(runs: ReadonlyArray<Run> | undefined): string | null {
  if (runs === undefined) return null;
  const active = runs.find((run) => ACTIVE_RUN_STATUSES.has(run.status));
  return active?.id ?? null;
}

function readCurrentTheme(): Theme {
  const attr = document.documentElement.getAttribute("data-theme");
  return attr === "dark" ? "dark" : "light";
}

function persistTheme(nextTheme: Theme): void {
  try {
    window.localStorage.setItem(STORAGE_KEYS.theme, nextTheme);
  } catch {
    /* non-fatal — palette remains usable without persistence */
  }
}

function buildNavCommands({
  navigate,
}: Pick<BuildCommandsParams, "navigate">): readonly CommandDefinition[] {
  const entries = NAV_GROUPS.flatMap((group) => group.items);
  const all = [...entries, SETTINGS_NAV_ITEM];
  return all.map((navItem) => ({
    id: `nav:${navItem.path}`,
    label: `Go to ${navItem.label}`,
    hint: "nav" as const,
    icon: HINT_ICON_BY_KIND.nav,
    run: (): void => {
      navigate(navItem.path);
    },
  }));
}

function buildActionCommands({
  navigate,
  toast,
  activeRunId,
}: Pick<BuildCommandsParams, "navigate" | "toast" | "activeRunId">): readonly CommandDefinition[] {
  const navigateWithToast = ({ path, toastTitle }: NavigateWithToastParams): void => {
    navigate(path);
    toast({ title: toastTitle, variant: "info" });
  };
  return [
    {
      id: "action:start-run",
      label: "Start new training run",
      hint: "action",
      icon: HINT_ICON_BY_KIND.action,
      run: (): void =>
        navigateWithToast({ path: "/training", toastTitle: "Training wizard opened" }),
    },
    {
      id: "action:compare-runs",
      label: "Compare last 2 runs",
      hint: "action",
      icon: HINT_ICON_BY_KIND.action,
      run: (): void => {
        navigate("/compare");
      },
    },
    {
      id: "action:pause-run",
      label: "Pause current run",
      hint: "action",
      icon: HINT_ICON_BY_KIND.action,
      run: (): void => {
        if (activeRunId === null) {
          toast({ title: "No active run to pause", variant: "warn" });
          return;
        }
        toast({ title: `Paused ${activeRunId}`, variant: "warn" });
      },
    },
    {
      id: "action:stop-run",
      label: "Stop current run",
      hint: "action",
      icon: HINT_ICON_BY_KIND.action,
      run: (): void => {
        if (activeRunId === null) {
          toast({ title: "No active run to stop", variant: "warn" });
          return;
        }
        toast({ title: `Stopped ${activeRunId}`, variant: "danger" });
      },
    },
    {
      id: "action:new-eval",
      label: "Create new eval",
      hint: "action",
      icon: HINT_ICON_BY_KIND.action,
      run: (): void => navigateWithToast({ path: "/eval", toastTitle: "New evaluation" }),
    },
  ];
}

function buildPrefCommands({
  toast,
  openTweaks,
}: Pick<BuildCommandsParams, "toast" | "openTweaks">): readonly CommandDefinition[] {
  return [
    {
      id: "pref:switch-theme",
      label: "Switch theme",
      hint: "pref",
      icon: HINT_ICON_BY_KIND.pref,
      run: (): void => {
        const current = readCurrentTheme();
        const next: Theme = current === "dark" ? "light" : "dark";
        if (!THEME_VALUES.includes(next)) return;
        document.documentElement.setAttribute("data-theme", next);
        persistTheme(next);
        toast({ title: `Switched to ${next} theme`, variant: "info" });
      },
    },
    {
      id: "pref:open-tweaks",
      label: "Open Tweaks",
      hint: "pref",
      icon: SlidersHorizontal,
      run: openTweaks,
    },
  ];
}

function buildCommands({
  navigate,
  toast,
  openTweaks,
  activeRunId,
}: BuildCommandsParams): readonly CommandDefinition[] {
  return [
    ...buildNavCommands({ navigate }),
    ...buildActionCommands({ navigate, toast, activeRunId }),
    ...buildPrefCommands({ toast, openTweaks }),
  ];
}

interface CommandGroupViewProps {
  readonly hint: CommandHint;
  readonly commands: readonly CommandDefinition[];
  readonly onSelect: (command: CommandDefinition) => void;
}

function CommandGroupView({
  hint,
  commands,
  onSelect,
}: CommandGroupViewProps): React.JSX.Element | null {
  if (commands.length === 0) return null;
  return (
    <CommandPrimitive.Group
      heading={HINT_GROUP_LABEL[hint]}
      className={cn(
        "overflow-hidden px-2 pb-2",
        "[&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5",
        "[&_[cmdk-group-heading]]:font-mono [&_[cmdk-group-heading]]:text-[10px]",
        "[&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-[0.08em]",
        "[&_[cmdk-group-heading]]:text-ink-4",
      )}
    >
      {commands.map((command) => {
        const IconComponent = command.icon;
        return (
          <CommandPrimitive.Item
            key={command.id}
            value={command.label}
            onSelect={(): void => onSelect(command)}
            className={cn(
              "relative flex cursor-pointer select-none items-center gap-2.5 rounded-sm",
              "px-2 py-1.5 text-[13px] text-ink-1 outline-none",
              "data-[selected=true]:bg-surface-2",
              "[&_svg]:h-3.5 [&_svg]:w-3.5 [&_svg]:shrink-0 [&_svg]:text-ink-3",
            )}
          >
            <IconComponent />
            <span className="flex-1 truncate">{command.label}</span>
            <span
              className={cn(
                "inline-flex items-center justify-center px-1.5 py-0.5 rounded",
                "border border-hairline bg-surface-2",
                "font-mono text-[9px] uppercase tracking-[0.08em] text-ink-3",
              )}
            >
              {command.hint}
            </span>
          </CommandPrimitive.Item>
        );
      })}
    </CommandPrimitive.Group>
  );
}

export function CommandPalette(): React.JSX.Element {
  const isOpen = useAppStore((state) => state.isCommandPaletteOpen);
  const setCommandPaletteOpen = useAppStore((state) => state.setCommandPaletteOpen);
  const setTweaksPanelOpen = useAppStore((state) => state.setTweaksPanelOpen);
  const activeProjectId = useAppStore((state) => state.activeProjectId) ?? "";
  const navigate = useNavigate();
  const { toast } = useToast();
  const { data: runs } = useRuns({ projectId: activeProjectId });
  const activeRunId = findActiveRunId(runs);

  const handleClose = React.useCallback((): void => {
    setCommandPaletteOpen(false);
  }, [setCommandPaletteOpen]);

  const handleOpenTweaks = React.useCallback((): void => {
    setTweaksPanelOpen(true);
  }, [setTweaksPanelOpen]);

  const commands = React.useMemo(
    () => buildCommands({ navigate, toast, openTweaks: handleOpenTweaks, activeRunId }),
    [navigate, toast, handleOpenTweaks, activeRunId],
  );

  const handleSelect = React.useCallback(
    (command: CommandDefinition): void => {
      handleClose();
      command.run();
    },
    [handleClose],
  );

  const commandsByHint = React.useMemo(() => {
    const grouped: Record<CommandHint, CommandDefinition[]> = {
      nav: [],
      action: [],
      pref: [],
    };
    for (const command of commands) {
      grouped[command.hint].push(command);
    }
    return grouped;
  }, [commands]);

  return (
    <DialogPrimitive.Root
      open={isOpen}
      onOpenChange={(nextOpen): void => setCommandPaletteOpen(nextOpen)}
    >
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay
          className={cn(
            "fixed inset-0 z-[200] bg-[color-mix(in_oklch,black_45%,transparent)] backdrop-blur-sm",
            "animate-fade-in",
          )}
        />
        <DialogPrimitive.Content
          aria-label="Command palette"
          className={cn(
            "fixed left-1/2 top-[15vh] z-[201] w-full max-w-[560px] -translate-x-1/2",
            "overflow-hidden rounded-lg border border-hairline bg-surface shadow-token-lg",
            "animate-fade-up",
          )}
          onOpenAutoFocus={(event): void => {
            event.preventDefault();
          }}
        >
          <DialogPrimitive.Title className="sr-only">Command palette</DialogPrimitive.Title>
          <DialogPrimitive.Description className="sr-only">
            Search for commands, pages, and preferences.
          </DialogPrimitive.Description>
          <CommandPrimitive label="Command palette" className="flex h-full w-full flex-col" loop>
            <div className="flex items-center gap-2 border-b border-hairline px-3.5 py-2.5">
              <Search className="h-4 w-4 text-ink-3" aria-hidden="true" />
              <CommandPrimitive.Input
                autoFocus
                placeholder="Type a command or search..."
                className={cn(
                  "flex h-8 w-full bg-transparent text-[13px] text-ink-1",
                  "outline-none placeholder:text-ink-4",
                )}
              />
              <Kbd>ESC</Kbd>
            </div>
            <CommandPrimitive.List className="max-h-[360px] overflow-y-auto overflow-x-hidden py-1">
              <CommandPrimitive.Empty className="px-4 py-6 text-center font-mono text-[11px] text-ink-3">
                No matches
              </CommandPrimitive.Empty>
              {HINT_ORDER.map((hint) => (
                <CommandGroupView
                  key={hint}
                  hint={hint}
                  commands={commandsByHint[hint]}
                  onSelect={handleSelect}
                />
              ))}
            </CommandPrimitive.List>
            <div
              className={cn(
                "flex items-center gap-4 border-t border-hairline bg-surface-2 px-3.5 py-2",
                "font-mono text-[10px] text-ink-3",
              )}
            >
              <span className="inline-flex items-center gap-1.5">
                <Kbd>↑↓</Kbd> navigate
              </span>
              <span className="inline-flex items-center gap-1.5">
                <Kbd>↵</Kbd> select
              </span>
              <span className="inline-flex items-center gap-1.5">
                <Kbd>ESC</Kbd> close
              </span>
            </div>
          </CommandPrimitive>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
