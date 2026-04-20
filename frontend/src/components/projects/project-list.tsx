import * as React from "react";
import { MoreVertical, Trash2 } from "lucide-react";
import type { Project } from "@/types/project";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { StatusDot } from "@/components/shared/status-dot";
import { RunRow, RunRowCell } from "@/components/shared/run-row";

interface ProjectListProps {
  readonly projects: ReadonlyArray<Project>;
  readonly selectedProjectId?: string | null;
  readonly onSelect: (projectId: string) => void;
  readonly onDelete: (projectId: string) => void;
}

const LIST_GRID_TEMPLATE = "16px 1.2fr 150px 120px 100px 90px 32px";

function formatRelative(iso: string): string {
  const then = new Date(iso).getTime();
  const now = Date.now();
  const diffMs = Math.max(0, now - then);
  const mins = Math.floor(diffMs / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}

export function ProjectList({
  projects,
  selectedProjectId = null,
  onSelect,
  onDelete,
}: ProjectListProps): React.JSX.Element {
  if (projects.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 font-mono text-[12px] text-ink-3">
        <p>No projects yet. Create one to get started.</p>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-lg border border-hairline bg-surface">
      <RunRow isHeader style={{ gridTemplateColumns: LIST_GRID_TEMPLATE }}>
        <span />
        <RunRowCell>name</RunRowCell>
        <RunRowCell>base model</RunRowCell>
        <RunRowCell>method</RunRowCell>
        <RunRowCell>status</RunRowCell>
        <RunRowCell align="end">updated</RunRowCell>
        <span />
      </RunRow>
      {projects.map((project) => {
        const { id, name, description, updatedAt } = project;
        return (
          <RunRow
            key={id}
            selected={selectedProjectId === id}
            onClick={() => onSelect(id)}
            style={{ gridTemplateColumns: LIST_GRID_TEMPLATE }}
          >
            <StatusDot status="pending" />
            <div className="min-w-0">
              <div className="truncate text-[13px] font-medium text-ink-1">{name}</div>
              <div className="truncate font-mono text-[10.5px] text-ink-3">
                {description || "—"}
              </div>
            </div>
            <RunRowCell>—</RunRowCell>
            <RunRowCell>—</RunRowCell>
            <RunRowCell>idle</RunRowCell>
            <RunRowCell align="end">{formatRelative(updatedAt)}</RunRowCell>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 opacity-0 transition-opacity group-hover:opacity-100 focus:opacity-100"
                  aria-label={`Project actions for ${name}`}
                  onClick={(event) => event.stopPropagation()}
                >
                  <MoreVertical className="h-3.5 w-3.5" aria-hidden="true" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem
                  onClick={(event) => {
                    event.stopPropagation();
                    onDelete(id);
                  }}
                  className="text-[color:var(--danger)]"
                >
                  <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                  Delete project
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </RunRow>
        );
      })}
    </div>
  );
}
