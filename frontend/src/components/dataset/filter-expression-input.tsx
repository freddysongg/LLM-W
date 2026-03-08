import * as React from "react";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";

interface FilterExpressionInputProps {
  readonly value: string;
  readonly onChange: (value: string) => void;
}

export function FilterExpressionInput({
  value,
  onChange,
}: FilterExpressionInputProps): React.JSX.Element {
  return (
    <div className="space-y-2">
      <Label htmlFor="filter-expression">Filter Expression</Label>
      <Input
        id="filter-expression"
        type="text"
        placeholder="e.g. len(row['response']) > 50 and row['category'] == 'science'"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
      <p className="text-xs text-muted-foreground">
        Optional Python expression evaluated against each row. Leave blank to include all rows.
      </p>
    </div>
  );
}
