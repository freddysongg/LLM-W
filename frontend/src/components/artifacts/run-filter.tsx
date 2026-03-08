import * as React from "react";
import type { Run } from "@/types/run";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface RunFilterProps {
  readonly runs: ReadonlyArray<Run>;
  readonly value: string | undefined;
  readonly onChange: (runId: string | undefined) => void;
}

export function RunFilter({ runs, value, onChange }: RunFilterProps): React.JSX.Element {
  const handleChange = (selected: string): void => {
    onChange(selected === "all" ? undefined : selected);
  };

  return (
    <Select value={value ?? "all"} onValueChange={handleChange}>
      <SelectTrigger className="w-52">
        <SelectValue placeholder="All runs" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="all">All runs</SelectItem>
        {runs.map((run) => (
          <SelectItem key={run.id} value={run.id}>
            Run {run.id.slice(0, 8)}… ({run.status})
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
