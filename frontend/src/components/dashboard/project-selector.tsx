import * as React from "react";
import { useState } from "react";
import { Check, ChevronsUpDown } from "lucide-react";
import type { Project } from "@/types/project";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface ProjectSelectorProps {
  readonly projects: ReadonlyArray<Project>;
  readonly selectedProjectId: string | null;
  readonly onSelect: (projectId: string) => void;
}

export function ProjectSelector({
  projects,
  selectedProjectId,
  onSelect,
}: ProjectSelectorProps): React.JSX.Element {
  const [isOpen, setIsOpen] = useState(false);

  const selectedProject = projects.find((p) => p.id === selectedProjectId);

  const handleSelect = (projectId: string): void => {
    onSelect(projectId);
    setIsOpen(false);
  };

  return (
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={isOpen}
          aria-label="Select a project"
          className="w-64 justify-between"
        >
          <span className="truncate">
            {selectedProject ? selectedProject.name : "Select a project..."}
          </span>
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-64 p-0">
        <Command>
          <CommandInput placeholder="Search projects..." />
          <CommandList>
            <CommandEmpty>No projects found.</CommandEmpty>
            <CommandGroup>
              {projects.map((project) => (
                <CommandItem
                  key={project.id}
                  value={project.name}
                  onSelect={() => handleSelect(project.id)}
                >
                  <Check
                    className={cn(
                      "mr-2 h-4 w-4",
                      selectedProjectId === project.id ? "opacity-100" : "opacity-0",
                    )}
                  />
                  {project.name}
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
