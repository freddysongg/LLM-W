import * as React from "react";
import type { DatasetFormat } from "@/types/config";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface FormatSelectorProps {
  readonly value: DatasetFormat;
  readonly onChange: (format: DatasetFormat) => void;
}

const FORMAT_OPTIONS: ReadonlyArray<{ value: DatasetFormat; label: string }> = [
  { value: "default", label: "Default (auto-detect)" },
  { value: "sharegpt", label: "ShareGPT" },
  { value: "openai", label: "OpenAI Messages" },
  { value: "alpaca", label: "Alpaca" },
  { value: "custom", label: "Custom (requires field mapping)" },
];

export function FormatSelector({ value, onChange }: FormatSelectorProps): React.JSX.Element {
  return (
    <div className="space-y-2">
      <Label htmlFor="dataset-format">Format</Label>
      <Select value={value} onValueChange={(val) => onChange(val as DatasetFormat)}>
        <SelectTrigger id="dataset-format">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {FORMAT_OPTIONS.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
