import * as React from "react";
import { Download, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { Project, CreateProjectRequest } from "@/types/project";

interface ImportExportActionsProps {
  readonly selectedProject: Project | null;
  readonly onImport: (request: CreateProjectRequest) => void;
  readonly isImporting: boolean;
}

interface ProjectExportShape {
  readonly name: string;
  readonly description: string;
}

function isProjectExportShape(value: unknown): value is ProjectExportShape {
  if (typeof value !== "object" || value === null) return false;
  const obj = value as Record<string, unknown>;
  return typeof obj["name"] === "string";
}

export function ImportExportActions({
  selectedProject,
  onImport,
  isImporting,
}: ImportExportActionsProps): React.JSX.Element {
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const handleExport = (): void => {
    if (!selectedProject) return;
    const { name, description, id, createdAt, updatedAt } = selectedProject;
    const exportData = { name, description, id, createdAt, updatedAt };
    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${name.replace(/\s+/g, "-").toLowerCase()}-export.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const handleImportClick = (): void => {
    fileInputRef.current?.click();
  };

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>): void => {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const parsed: unknown = JSON.parse(e.target?.result as string);
        if (!isProjectExportShape(parsed)) {
          throw new Error("Invalid project export file: missing required name field.");
        }
        onImport({
          name: parsed.name,
          description: parsed.description ?? "",
        });
      } catch (err) {
        // Non-JSON or invalid shape — surface via console; caller handles UI
        console.error("Failed to parse project import file:", err);
      }
    };
    reader.readAsText(file);
    // Reset so the same file can be re-selected if needed
    event.target.value = "";
  };

  return (
    <div className="flex items-center gap-2">
      <Button
        variant="outline"
        size="sm"
        onClick={handleExport}
        disabled={!selectedProject}
        title={selectedProject ? "Export project metadata as JSON" : "Select a project to export"}
      >
        <Download className="h-4 w-4 mr-1" />
        Export
      </Button>
      <Button variant="outline" size="sm" onClick={handleImportClick} disabled={isImporting}>
        <Upload className="h-4 w-4 mr-1" />
        {isImporting ? "Importing..." : "Import"}
      </Button>
      <input
        ref={fileInputRef}
        type="file"
        accept=".json,application/json"
        className="hidden"
        onChange={handleFileChange}
        aria-hidden="true"
      />
    </div>
  );
}
