import * as React from "react";
import { Trash2 } from "lucide-react";
import type { Project } from "@/types/project";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";

interface ProjectListProps {
  readonly projects: ReadonlyArray<Project>;
  readonly onSelect: (projectId: string) => void;
  readonly onDelete: (projectId: string) => void;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function ProjectList({ projects, onSelect, onDelete }: ProjectListProps): React.JSX.Element {
  if (projects.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
        <p className="text-sm">No projects yet. Create one to get started.</p>
      </div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Name</TableHead>
          <TableHead>Description</TableHead>
          <TableHead>Last Updated</TableHead>
          <TableHead className="w-16" />
        </TableRow>
      </TableHeader>
      <TableBody>
        {projects.map((project) => (
          <TableRow key={project.id}>
            <TableCell>
              <button
                className="font-medium text-foreground hover:underline text-left"
                onClick={() => onSelect(project.id)}
                type="button"
              >
                {project.name}
              </button>
            </TableCell>
            <TableCell className="text-muted-foreground max-w-xs truncate">
              {project.description || <span className="italic">No description</span>}
            </TableCell>
            <TableCell className="text-muted-foreground whitespace-nowrap">
              {formatDate(project.updatedAt)}
            </TableCell>
            <TableCell>
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Delete project ${project.name}`}
                onClick={() => onDelete(project.id)}
              >
                <Trash2 className="h-4 w-4 text-destructive" />
              </Button>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
