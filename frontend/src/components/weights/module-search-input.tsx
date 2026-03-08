import * as React from "react";
import { Input } from "@/components/ui/input";

interface ModuleSearchInputProps {
  readonly value: string;
  readonly onChange: (value: string) => void;
  readonly placeholder?: string;
}

export function ModuleSearchInput({
  value,
  onChange,
  placeholder = "Search modules…",
}: ModuleSearchInputProps): React.JSX.Element {
  return (
    <Input
      type="search"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className="h-8 text-sm"
    />
  );
}
