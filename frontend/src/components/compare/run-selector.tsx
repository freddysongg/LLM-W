import * as React from "react";
import { Check, ChevronsUpDown, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { Run } from "@/types/run";

interface RunSelectorProps {
  readonly runs: ReadonlyArray<Run>;
  readonly selectedRunIds: ReadonlyArray<string>;
  readonly onSelectionChange: (runIds: ReadonlyArray<string>) => void;
}

type BadgeVariant = "default" | "secondary" | "destructive" | "outline";

function statusVariant(status: Run["status"]): BadgeVariant {
  switch (status) {
    case "running":
      return "default";
    case "completed":
      return "secondary";
    case "failed":
      return "destructive";
    case "cancelled":
    case "paused":
    case "pending":
      return "outline";
    default: {
      const _exhaustive: never = status;
      return _exhaustive;
    }
  }
}

function formatRunLabel(run: Run): string {
  return `Run ${run.id.slice(0, 8)} (${run.status})`;
}

export function RunSelector({
  runs,
  selectedRunIds,
  onSelectionChange,
}: RunSelectorProps): React.JSX.Element {
  const [isOpen, setIsOpen] = React.useState(false);

  const toggleRun = (runId: string): void => {
    const isSelected = selectedRunIds.includes(runId);
    if (isSelected) {
      onSelectionChange(selectedRunIds.filter((id) => id !== runId));
    } else {
      onSelectionChange([...selectedRunIds, runId]);
    }
  };

  const removeRun = (runId: string): void => {
    onSelectionChange(selectedRunIds.filter((id) => id !== runId));
  };

  const selectedRuns = selectedRunIds
    .map((id) => runs.find((r) => r.id === id))
    .filter((r): r is Run => r !== undefined);

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Popover open={isOpen} onOpenChange={setIsOpen}>
        <PopoverTrigger asChild>
          <Button
            variant="outline"
            role="combobox"
            aria-expanded={isOpen}
            aria-label="Select runs to compare"
            className="min-w-52 justify-between"
          >
            <span className="text-muted-foreground text-sm">
              {selectedRunIds.length === 0 ? "Select runs…" : `${selectedRunIds.length} selected`}
            </span>
            <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-72 p-0" align="start">
          <Command>
            <CommandInput placeholder="Search runs…" />
            <CommandList>
              <CommandEmpty>No runs found.</CommandEmpty>
              <CommandGroup>
                {runs.map((run) => {
                  const isSelected = selectedRunIds.includes(run.id);
                  return (
                    <CommandItem key={run.id} value={run.id} onSelect={() => toggleRun(run.id)}>
                      <Check
                        className={cn("mr-2 h-4 w-4", isSelected ? "opacity-100" : "opacity-0")}
                      />
                      <span className="font-mono text-xs flex-1">{run.id.slice(0, 8)}</span>
                      <Badge variant={statusVariant(run.status)} className="ml-2 text-xs">
                        {run.status}
                      </Badge>
                    </CommandItem>
                  );
                })}
              </CommandGroup>
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>

      {selectedRuns.map((run) => (
        <Badge key={run.id} variant="secondary" className="gap-1 pr-1 font-mono text-xs">
          {formatRunLabel(run)}
          <button
            type="button"
            onClick={() => removeRun(run.id)}
            aria-label={`Remove ${run.id.slice(0, 8)} from comparison`}
            className="ml-1 rounded hover:bg-muted"
          >
            <X className="h-3 w-3" />
          </button>
        </Badge>
      ))}
    </div>
  );
}
