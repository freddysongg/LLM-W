import * as React from "react";
import { useNavigate } from "react-router-dom";
import { BarChart3, ClipboardList, Play, Sparkles } from "lucide-react";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Kbd } from "@/components/ui/kbd";
import { cn } from "@/lib/utils";

interface QuickLaunchActionsProps {
  readonly hasActiveProject: boolean;
}

type QuickLaunchId = "training" | "eval" | "compare" | "suggestions";

interface QuickLaunchTile {
  readonly id: QuickLaunchId;
  readonly title: string;
  readonly description: string;
  readonly Icon: typeof Play;
  readonly path: string;
}

const QUICK_LAUNCH_TILES: ReadonlyArray<QuickLaunchTile> = [
  {
    id: "training",
    title: "Start training",
    description: "Launch a new run from active config",
    Icon: Play,
    path: "/training",
  },
  {
    id: "eval",
    title: "Run evaluation",
    description: "Judge on frozen eval split",
    Icon: ClipboardList,
    path: "/eval",
  },
  {
    id: "compare",
    title: "Compare runs",
    description: "Diff metrics and configs side-by-side",
    Icon: BarChart3,
    path: "/compare",
  },
  {
    id: "suggestions",
    title: "AI suggestions",
    description: "Rule-engine and LLM-based tweaks",
    Icon: Sparkles,
    path: "/suggestions",
  },
];

export function QuickLaunchActions({
  hasActiveProject,
}: QuickLaunchActionsProps): React.JSX.Element {
  const navigate = useNavigate();

  const handleTileClick = (path: string): void => {
    if (!hasActiveProject) return;
    void navigate(path);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Quick launch</CardTitle>
        <Kbd>⌘J</Kbd>
      </CardHeader>
      <div className="grid grid-cols-2 gap-px bg-hairline">
        {QUICK_LAUNCH_TILES.map(({ id, title, description, Icon, path }) => (
          <button
            key={id}
            type="button"
            disabled={!hasActiveProject}
            onClick={() => handleTileClick(path)}
            className={cn(
              "flex flex-col items-start gap-1.5 bg-surface p-4 text-left",
              "transition-colors duration-[var(--dur-1)]",
              "hover:bg-surface-2 focus-visible:outline-none focus-visible:[box-shadow:var(--focus-ring)]",
              "disabled:cursor-not-allowed disabled:opacity-50",
            )}
          >
            <span className="grid size-7 place-items-center rounded-md bg-surface-2 text-ink-2">
              <Icon className="size-3.5" aria-hidden="true" />
            </span>
            <span className="text-[12.5px] font-medium text-ink-1">{title}</span>
            <span className="font-mono text-[10.5px] leading-snug text-ink-3">{description}</span>
          </button>
        ))}
      </div>
    </Card>
  );
}
