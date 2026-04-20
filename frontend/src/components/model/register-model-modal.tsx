import * as React from "react";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Callout } from "@/components/shared/callout";
import { cn } from "@/lib/utils";

type RegisterSource = "hf" | "local" | "s3";
type RegisterDtype = "bfloat16" | "float16" | "float32" | "int8" | "int4";

interface RegisterModelDraft {
  readonly source: RegisterSource;
  readonly path: string;
  readonly name: string;
  readonly dtype: RegisterDtype;
  readonly isPinned: boolean;
}

interface RegisterModelModalProps {
  readonly isOpen: boolean;
  readonly onOpenChange: (open: boolean) => void;
  readonly onRegister: (draft: RegisterModelDraft) => void;
}

interface SourceOption {
  readonly value: RegisterSource;
  readonly label: string;
}

const SOURCE_OPTIONS: ReadonlyArray<SourceOption> = [
  { value: "hf", label: "HuggingFace" },
  { value: "local", label: "Local path" },
  { value: "s3", label: "S3 / GCS" },
];

const DTYPE_OPTIONS: ReadonlyArray<RegisterDtype> = [
  "bfloat16",
  "float16",
  "float32",
  "int8",
  "int4",
];

const PATH_LABEL: Record<RegisterSource, string> = {
  hf: "HF repo",
  local: "Path",
  s3: "Bucket URI",
};

const PATH_PLACEHOLDER: Record<RegisterSource, string> = {
  hf: "Qwen/Qwen2.5-1.5B",
  local: "/models/qwen2.5-1.5b",
  s3: "s3://bucket/models/…",
};

const INITIAL_DRAFT: RegisterModelDraft = {
  source: "hf",
  path: "",
  name: "",
  dtype: "bfloat16",
  isPinned: true,
};

export function RegisterModelModal({
  isOpen,
  onOpenChange,
  onRegister,
}: RegisterModelModalProps): React.JSX.Element {
  const [draft, setDraft] = React.useState<RegisterModelDraft>(INITIAL_DRAFT);

  const handleSubmit = (): void => {
    onRegister(draft);
    setDraft(INITIAL_DRAFT);
    onOpenChange(false);
  };

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Register model</DialogTitle>
        </DialogHeader>

        <div className="flex flex-col gap-4 px-6 py-5">
          <div className="flex flex-col gap-1.5">
            <Label className="font-mono text-[10px] uppercase tracking-[0.08em] text-ink-3">
              Source
            </Label>
            <div
              role="radiogroup"
              aria-label="Source"
              className="inline-flex items-center gap-0.5 rounded-full border border-hairline bg-surface-2 p-[3px]"
            >
              {SOURCE_OPTIONS.map(({ value, label }) => {
                const isActive = draft.source === value;
                return (
                  <button
                    key={value}
                    type="button"
                    role="radio"
                    aria-checked={isActive}
                    onClick={() => setDraft((d) => ({ ...d, source: value }))}
                    className={cn(
                      "inline-flex flex-1 items-center justify-center rounded-full px-3 py-1",
                      "font-mono text-[10px] uppercase leading-none tracking-[0.08em]",
                      "transition-colors duration-[var(--dur-1)]",
                      isActive
                        ? "bg-ink-1 text-[color:var(--surface)]"
                        : "text-ink-2 hover:bg-surface-3 hover:text-ink-1",
                    )}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label
              htmlFor="register-path"
              className="font-mono text-[10px] uppercase tracking-[0.08em] text-ink-3"
            >
              {PATH_LABEL[draft.source]}
            </Label>
            <Input
              id="register-path"
              mono
              value={draft.path}
              onChange={(event) => setDraft((d) => ({ ...d, path: event.target.value }))}
              placeholder={PATH_PLACEHOLDER[draft.source]}
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label
              htmlFor="register-name"
              className="font-mono text-[10px] uppercase tracking-[0.08em] text-ink-3"
            >
              Local name
            </Label>
            <Input
              id="register-name"
              mono
              value={draft.name}
              onChange={(event) => setDraft((d) => ({ ...d, name: event.target.value }))}
              placeholder="qwen2.5-1.5b"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label
                htmlFor="register-dtype"
                className="font-mono text-[10px] uppercase tracking-[0.08em] text-ink-3"
              >
                Dtype
              </Label>
              <Select
                value={draft.dtype}
                onValueChange={(value) =>
                  setDraft((d) => ({ ...d, dtype: value as RegisterDtype }))
                }
              >
                <SelectTrigger id="register-dtype">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {DTYPE_OPTIONS.map((value) => (
                    <SelectItem key={value} value={value}>
                      {value}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="flex flex-col gap-1.5">
              <Label
                htmlFor="register-pin"
                className="font-mono text-[10px] uppercase tracking-[0.08em] text-ink-3"
              >
                Pin to project
              </Label>
              <div className="flex h-8 items-center gap-2">
                <Switch
                  id="register-pin"
                  checked={draft.isPinned}
                  onCheckedChange={(checked) => setDraft((d) => ({ ...d, isPinned: checked }))}
                />
                <span className="font-mono text-[11px] text-ink-2">
                  {draft.isPinned ? "pinned" : "not pinned"}
                </span>
              </div>
            </div>
          </div>

          <Callout tone="iris">
            <span className="font-mono text-[11px] text-ink-2">
              $ llm-w register --source {draft.source} {draft.path || "<path>"}
            </span>
          </Callout>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button variant="primary" onClick={handleSubmit}>
            Register
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
