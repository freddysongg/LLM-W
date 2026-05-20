import { NavLink } from "react-router-dom";
import { ChevronRight, Settings, LogOut } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/stores/app-store";
import type { NavGroupKey } from "@/stores/app-store";
import { NAV_GROUPS, NAV_ICON_COMPONENTS, SETTINGS_NAV_ITEM } from "@/lib/nav";
import type { NavItem } from "@/lib/nav";
import { useToast } from "@/hooks/use-toast";
import { useRunStreamStore } from "@/stores/run-stream-store";
import { CURRENT_USER } from "@/lib/current-user";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface SidebarItemProps {
  readonly item: NavItem;
  readonly collapsed: boolean;
  readonly hasLiveBadge: boolean;
}

function SidebarItem({ item, collapsed, hasLiveBadge }: SidebarItemProps): React.JSX.Element {
  const { label, path, icon, badge } = item;
  const IconComponent = NAV_ICON_COMPONENTS[icon];
  const shouldShowBadge = Boolean(badge) && hasLiveBadge && !collapsed;

  return (
    <NavLink
      to={path}
      end={path === "/"}
      title={collapsed ? label : undefined}
      className={({ isActive }) =>
        cn(
          "relative flex items-center gap-2.5 px-2.5 py-[7px] rounded-[10px] text-[13px] font-[450] text-ink-3 transition-colors hover:bg-surface hover:text-ink-1",
          collapsed && "justify-center p-[10px]",
          isActive && "bg-surface text-ink-1 font-medium shadow-xs",
        )
      }
    >
      {({ isActive }) => (
        <>
          {isActive && (
            <span
              aria-hidden="true"
              className="absolute -left-2 top-1/2 -translate-y-1/2 w-[3px] h-[18px] rounded-r-[2px] animate-fade-in"
              style={{ background: "var(--ink-1)" }}
            />
          )}
          <IconComponent className="h-4 w-4 shrink-0 opacity-85" />
          {!collapsed && <span className="flex-1 truncate">{label}</span>}
          {shouldShowBadge && (
            <span className="inline-flex items-center gap-1 px-1.5 py-[1px] rounded-full border border-info/30 bg-info/10 text-[9px] font-mono font-medium uppercase tracking-wider text-info">
              <span
                aria-hidden="true"
                className="h-1.5 w-1.5 rounded-full animate-pulse-dot"
                style={{ background: "var(--info)" }}
              />
              {badge}
            </span>
          )}
        </>
      )}
    </NavLink>
  );
}

interface NavGroupBlockProps {
  readonly groupKey: NavGroupKey;
  readonly label: string;
  readonly items: readonly NavItem[];
  readonly collapsed: boolean;
  readonly hasActiveRunStream: boolean;
}

function NavGroupBlock({
  groupKey,
  label,
  items,
  collapsed,
  hasActiveRunStream,
}: NavGroupBlockProps): React.JSX.Element {
  const isOpen = useAppStore((state) => state.navGroupExpanded[groupKey]);
  const toggleNavGroup = useAppStore((state) => state.toggleNavGroup);

  return (
    <div className="mb-3.5">
      {!collapsed && (
        <button
          type="button"
          onClick={() => toggleNavGroup(groupKey)}
          className="w-full px-2.5 pt-1 pb-1.5 flex items-center gap-1.5 font-mono text-[10px] font-medium uppercase tracking-[0.12em] text-ink-4 hover:text-ink-3 transition-colors"
          aria-expanded={isOpen}
        >
          <ChevronRight
            className={cn(
              "h-2.5 w-2.5 shrink-0 opacity-70 transition-transform duration-150",
              isOpen && "rotate-90",
            )}
          />
          <span>{label}</span>
        </button>
      )}
      {(collapsed || isOpen) && (
        <div className="flex flex-col gap-[2px] mt-[2px]">
          {items.map((item) => (
            <SidebarItem
              key={item.path}
              item={item}
              collapsed={collapsed}
              hasLiveBadge={item.badge === "LIVE" ? hasActiveRunStream : false}
            />
          ))}
        </div>
      )}
    </div>
  );
}

interface SidebarBrandProps {
  readonly collapsed: boolean;
  readonly onToggleCollapse: () => void;
}

function SidebarBrand({ collapsed, onToggleCollapse }: SidebarBrandProps): React.JSX.Element {
  return (
    <div
      className={cn(
        "flex items-center gap-2.5 h-[54px] px-4 border-b border-hairline shrink-0",
        collapsed && "px-0 justify-center relative",
      )}
    >
      <div
        className={cn(
          "grid place-items-center w-[22px] h-[22px] text-ink-1 shrink-0",
          collapsed && "m-0",
        )}
        aria-hidden="true"
      >
        <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
          <rect
            x="3.5"
            y="3.5"
            width="15"
            height="15"
            rx="3"
            stroke="currentColor"
            strokeWidth="1.4"
            transform="rotate(45 11 11)"
          />
          <circle cx="11" cy="11" r="2.4" fill="currentColor" />
        </svg>
      </div>
      {!collapsed && (
        <div className="flex-1 min-w-0 flex flex-col">
          <div className="font-mono text-[13px] font-semibold tracking-[-0.01em] text-ink-1 truncate">
            LLM-W
          </div>
          <div className="font-mono text-[10px] text-ink-3 uppercase tracking-[0.08em] mt-0.5">
            Workbench
          </div>
        </div>
      )}
      <button
        type="button"
        onClick={onToggleCollapse}
        aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        title={collapsed ? "Expand sidebar (⌘\\)" : "Collapse sidebar (⌘\\)"}
        className={cn(
          "grid place-items-center w-6 h-6 rounded-[6px] border border-hairline bg-transparent text-ink-3 shrink-0 hover:bg-surface hover:text-ink-1 hover:border-hairline-strong transition-colors",
          collapsed && "absolute -right-3 top-4 bg-surface shadow-token-sm z-10",
        )}
      >
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
          <path
            d={collapsed ? "M 5 3 L 9 7 L 5 11" : "M 9 3 L 5 7 L 9 11"}
            stroke="currentColor"
            strokeWidth="1.4"
            fill="none"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>
    </div>
  );
}

interface SidebarFooterProps {
  readonly collapsed: boolean;
}

function SidebarFooter({ collapsed }: SidebarFooterProps): React.JSX.Element {
  const { toast } = useToast();
  const { name, email, initials } = CURRENT_USER;

  const handleShowToast = (title: string): void => {
    toast({ title });
  };

  return (
    <div
      className={cn(
        "border-t border-hairline px-3 py-2.5 flex items-center gap-2.5 shrink-0",
        collapsed && "justify-center px-2.5",
      )}
    >
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            className={cn(
              "flex items-center gap-2.5 w-full rounded-[10px] p-1 hover:bg-surface transition-colors",
              collapsed && "justify-center p-[10px]",
            )}
            aria-label="Account menu"
          >
            <div
              className="w-7 h-7 rounded-full grid place-items-center font-mono text-[11px] font-semibold text-white shrink-0"
              style={{ background: "linear-gradient(135deg, var(--iris-3), var(--iris-4))" }}
              aria-hidden="true"
            >
              {initials}
            </div>
            {!collapsed && (
              <div className="flex-1 min-w-0 text-left">
                <div className="text-[12px] font-medium text-ink-1 truncate">{name}</div>
                <div className="font-mono text-[10px] text-ink-3 truncate">{email}</div>
              </div>
            )}
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          align="end"
          side="top"
          sideOffset={10}
          collisionPadding={16}
          className="w-56"
        >
          <DropdownMenuLabel>{email}</DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuItem asChild>
            <NavLink to={SETTINGS_NAV_ITEM.path} className="cursor-pointer">
              <Settings className="h-4 w-4" />
              <span>Settings</span>
            </NavLink>
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            onSelect={() => handleShowToast("Signed out — stubbed")}
            className="text-danger focus:text-danger"
          >
            <LogOut className="h-4 w-4" />
            <span>Sign out</span>
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}

function useHasActiveRunStream(): boolean {
  return useRunStreamStore((state) =>
    Object.values(state.runData).some(
      (entry) => entry.progressPct !== null && (entry.progressPct ?? 0) < 100,
    ),
  );
}

export function Sidebar(): React.JSX.Element {
  const isSidebarCollapsed = useAppStore((state) => state.isSidebarCollapsed);
  const toggleSidebar = useAppStore((state) => state.toggleSidebar);
  const hasActiveRunStream = useHasActiveRunStream();

  return (
    <aside
      className={cn(
        "flex flex-col h-screen shrink-0 border-r border-hairline bg-surface-2 transition-[width] duration-[260ms] ease-out overflow-hidden",
        isSidebarCollapsed ? "w-[60px]" : "w-60",
      )}
      style={{ transitionTimingFunction: "var(--ease-out)" }}
    >
      <SidebarBrand collapsed={isSidebarCollapsed} onToggleCollapse={toggleSidebar} />
      <nav className="flex-1 overflow-y-auto py-3 px-2" aria-label="Primary navigation">
        {NAV_GROUPS.map(({ key, label, items }) => (
          <NavGroupBlock
            key={key}
            groupKey={key as NavGroupKey}
            label={label}
            items={items}
            collapsed={isSidebarCollapsed}
            hasActiveRunStream={hasActiveRunStream}
          />
        ))}
      </nav>
      <SidebarFooter collapsed={isSidebarCollapsed} />
    </aside>
  );
}
