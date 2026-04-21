import * as React from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { tryParseYaml } from "@/lib/yaml-parse";

interface YamlEditorPaneProps {
  readonly initialYaml: string;
  readonly isSaving: boolean;
  readonly schemaErrors: ReadonlyArray<string>;
  readonly onDirtyChange: (isDirty: boolean) => void;
  readonly onSave: (yamlContent: string) => void;
  readonly onCancel: () => void;
}

export function YamlEditorPane({
  initialYaml,
  isSaving,
  schemaErrors,
  onDirtyChange,
  onSave,
  onCancel,
}: YamlEditorPaneProps): React.JSX.Element {
  const [value, setValue] = React.useState(initialYaml);
  const [parseError, setParseError] = React.useState<string | null>(null);

  React.useEffect(() => {
    setValue(initialYaml);
  }, [initialYaml]);

  const isDirty = value !== initialYaml;
  React.useEffect(() => {
    onDirtyChange(isDirty);
  }, [isDirty, onDirtyChange]);

  const handleSave = (): void => {
    const parsed = tryParseYaml(value);
    if (!parsed.ok) {
      const linePrefix = parsed.line !== null ? `line ${parsed.line}: ` : "";
      setParseError(`${linePrefix}${parsed.message}`);
      return;
    }
    setParseError(null);
    onSave(value);
  };

  return (
    <div className="flex flex-col gap-2">
      {parseError !== null ? (
        <div className="rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-[11px] font-mono text-red-700">
          {parseError}
        </div>
      ) : null}

      <Textarea
        value={value}
        onChange={(event) => setValue(event.target.value)}
        spellCheck={false}
        className="min-h-[360px] font-mono text-[11px] leading-relaxed"
      />

      {schemaErrors.length > 0 ? (
        <div className="flex flex-col gap-1 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2">
          <div className="font-mono text-[10px] uppercase tracking-wider text-amber-800">
            schema errors
          </div>
          {schemaErrors.map((error, idx) => (
            <div key={`err-${idx}`} className="font-mono text-[11px] text-amber-900">
              {error}
            </div>
          ))}
        </div>
      ) : null}

      <div className="flex justify-end gap-2 pt-1">
        <Button variant="outline" onClick={onCancel} disabled={isSaving}>
          Cancel
        </Button>
        <Button variant="primary" onClick={handleSave} disabled={isSaving}>
          {isSaving ? "Saving…" : "Save as new version"}
        </Button>
      </div>
    </div>
  );
}
