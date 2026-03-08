import * as React from "react";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

interface FieldMappingEditorProps {
  readonly mapping: Record<string, string>;
  readonly onChange: (mapping: Record<string, string>) => void;
}

interface MappingEntry {
  readonly id: string;
  readonly sourceField: string;
  readonly targetField: string;
}

function buildEntries(mapping: Record<string, string>): ReadonlyArray<MappingEntry> {
  return Object.entries(mapping).map(([sourceField, targetField], i) => ({
    id: String(i),
    sourceField,
    targetField,
  }));
}

export function FieldMappingEditor({
  mapping,
  onChange,
}: FieldMappingEditorProps): React.JSX.Element {
  const entries = buildEntries(mapping);

  const handleSourceChange = (oldSource: string, newSource: string): void => {
    const updated = { ...mapping };
    const targetValue = updated[oldSource];
    delete updated[oldSource];
    if (newSource) {
      updated[newSource] = targetValue ?? "";
    }
    onChange(updated);
  };

  const handleTargetChange = (sourceField: string, targetField: string): void => {
    onChange({ ...mapping, [sourceField]: targetField });
  };

  const handleRemove = (sourceField: string): void => {
    const updated = { ...mapping };
    delete updated[sourceField];
    onChange(updated);
  };

  const handleAdd = (): void => {
    onChange({ ...mapping, "": "" });
  };

  return (
    <div className="space-y-2">
      <Label>Field Mapping</Label>
      <div className="space-y-2">
        {entries.length === 0 && (
          <p className="text-xs text-muted-foreground">
            No field mappings. Add one to map source field names to expected names.
          </p>
        )}
        {entries.map(({ id, sourceField, targetField }) => (
          <div key={id} className="flex gap-2 items-center">
            <Input
              placeholder="source field"
              value={sourceField}
              onChange={(e) => handleSourceChange(sourceField, e.target.value)}
              className="flex-1 text-sm"
            />
            <span className="text-muted-foreground text-xs">→</span>
            <Input
              placeholder="target field"
              value={targetField}
              onChange={(e) => handleTargetChange(sourceField, e.target.value)}
              className="flex-1 text-sm"
            />
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => handleRemove(sourceField)}
              className="h-8 w-8 p-0 text-muted-foreground hover:text-destructive"
            >
              ×
            </Button>
          </div>
        ))}
        <Button type="button" variant="outline" size="sm" onClick={handleAdd} className="w-full">
          Add mapping
        </Button>
      </div>
    </div>
  );
}
