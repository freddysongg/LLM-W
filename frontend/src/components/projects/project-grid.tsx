import * as React from "react";
import { Star } from "lucide-react";
import type { Project } from "@/types/project";
import { Button } from "@/components/ui/button";

interface ProjectGridProps {
  readonly projects: ReadonlyArray<Project>;
  readonly onSelect: (projectId: string) => void;
}

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

function initialsFor(name: string): string {
  const trimmed = name.trim();
  if (trimmed.length === 0) return "??";
  return trimmed.slice(0, 2).toUpperCase();
}

interface ProjectThumbProps {
  readonly initials: string;
}

function ProjectThumb({ initials }: ProjectThumbProps): React.JSX.Element {
  return (
    <div
      className="relative aspect-[16/9] overflow-hidden"
      style={{ background: "var(--surface-3)" }}
      aria-hidden="true"
    >
      <div
        className="absolute inset-0"
        style={{
          background: [
            "radial-gradient(ellipse 60% 40% at 30% 30%, color-mix(in oklch, var(--iris-2) 55%, transparent), transparent 70%)",
            "radial-gradient(ellipse 60% 40% at 70% 70%, color-mix(in oklch, var(--iris-4) 45%, transparent), transparent 70%)",
          ].join(","),
          opacity: 0.6,
        }}
      />
      <div
        className="absolute bottom-2.5 left-2.5 grid h-[38px] w-[38px] place-items-center rounded-[10px] font-mono text-[12px] font-semibold tracking-[0.05em]"
        style={{ background: "var(--ink-1)", color: "var(--canvas)" }}
      >
        {initials}
      </div>
    </div>
  );
}

export function ProjectGrid({ projects, onSelect }: ProjectGridProps): React.JSX.Element {
  if (projects.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 font-mono text-[12px] text-ink-3">
        <p>No projects yet. Create one to get started.</p>
      </div>
    );
  }

  return (
    <div
      className="grid gap-4"
      style={{ gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))" }}
    >
      {projects.map((project) => {
        const { id, name, description, updatedAt } = project;
        return (
          <button
            key={id}
            type="button"
            onClick={() => onSelect(id)}
            className="group relative flex flex-col overflow-hidden rounded-lg border border-hairline bg-surface text-left shadow-xs transition-[transform,border-color,box-shadow] duration-[var(--dur-1)] hover:-translate-y-px hover:border-hairline-strong hover:shadow-token-sm focus-visible:outline-none focus-visible:[box-shadow:var(--focus-ring)]"
          >
            <ProjectThumb initials={initialsFor(name)} />
            <div className="flex flex-col gap-1 px-[14px] pb-[14px] pt-3">
              <div className="flex items-start justify-between gap-2">
                <div className="truncate text-[14px] font-semibold text-ink-1">{name}</div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 text-ink-3 opacity-0 transition-opacity group-hover:opacity-100 focus-visible:opacity-100"
                  aria-label={`Star project ${name}`}
                  onClick={(event) => event.stopPropagation()}
                >
                  <Star className="h-3.5 w-3.5" aria-hidden="true" />
                </Button>
              </div>
              <div className="truncate font-mono text-[11px] text-ink-3">{description || "—"}</div>
              <div className="mt-2 flex items-center justify-between font-mono text-[10px] text-ink-4">
                <span>updated</span>
                <span>{formatRelative(updatedAt)}</span>
              </div>
            </div>
          </button>
        );
      })}
    </div>
  );
}
