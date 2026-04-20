import * as React from "react";
import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

type FineTuneMethod = "full" | "lora" | "qlora" | "dpo";

const BASE_MODEL_OPTIONS: ReadonlyArray<string> = [
  "qwen2.5-1.5b",
  "qwen2.5-7b",
  "mistral-7b",
  "llama-3-8b",
  "tinyllama-1.1b",
  "phi-3-mini",
  "gemma-2b",
];

const FINE_TUNE_METHODS: ReadonlyArray<FineTuneMethod> = ["full", "lora", "qlora", "dpo"];

interface CreateProjectDialogProps {
  readonly isOpen: boolean;
  readonly onClose: () => void;
  readonly onCreate: (name: string, description: string) => void;
  readonly isCreating: boolean;
}

export function CreateProjectDialog({
  isOpen,
  onClose,
  onCreate,
  isCreating,
}: CreateProjectDialogProps): React.JSX.Element {
  const [name, setName] = useState<string>("");
  const [baseModel, setBaseModel] = useState<string>(BASE_MODEL_OPTIONS[0]);
  const [method, setMethod] = useState<FineTuneMethod>("lora");

  const handleSubmit = (event: React.FormEvent): void => {
    event.preventDefault();
    if (!name.trim()) return;
    const description = `Base: ${baseModel} · method: ${method}`;
    onCreate(name.trim(), description);
  };

  const handleOpenChange = (nextOpen: boolean): void => {
    if (!nextOpen) {
      setName("");
      setBaseModel(BASE_MODEL_OPTIONS[0]);
      setMethod("lora");
      onClose();
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <div className="flex flex-col gap-1.5">
            <DialogTitle>New project</DialogTitle>
            <DialogDescription>Set up a new fine-tuning project.</DialogDescription>
          </div>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4 px-6 py-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="project-name" className="text-[11px] text-ink-3">
              Name
            </Label>
            <Input
              id="project-name"
              placeholder="qwen2.5-1.5b-experiments"
              value={name}
              onChange={(event) => setName(event.target.value)}
              disabled={isCreating}
              required
              autoFocus
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="project-base" className="text-[11px] text-ink-3">
              Base model
            </Label>
            <select
              id="project-base"
              value={baseModel}
              onChange={(event) => setBaseModel(event.target.value)}
              disabled={isCreating}
              className="h-8 w-full rounded-md border border-hairline bg-surface px-3 text-[13px] text-ink-1 transition-[border-color,box-shadow] duration-[140ms] hover:border-hairline-strong focus:outline-none focus-visible:border-[color:var(--iris-3)] focus-visible:[box-shadow:var(--focus-ring)] disabled:cursor-not-allowed disabled:opacity-50"
            >
              {BASE_MODEL_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <span className="font-sans text-[11px] text-ink-3">Fine-tune method</span>
            <div
              className="inline-flex items-center gap-0.5 rounded-md border border-hairline bg-surface-2 p-0.5"
              role="radiogroup"
              aria-label="Fine-tune method"
            >
              {FINE_TUNE_METHODS.map((option) => {
                const isActive = method === option;
                return (
                  <button
                    key={option}
                    type="button"
                    role="radio"
                    aria-checked={isActive}
                    onClick={() => setMethod(option)}
                    className={cn(
                      "rounded-[4px] px-2.5 py-1 font-mono text-[11px] uppercase tracking-[0.04em] transition-colors",
                      "focus-visible:outline-none focus-visible:[box-shadow:var(--focus-ring)]",
                      isActive
                        ? "bg-surface text-ink-1 shadow-token-xs"
                        : "text-ink-3 hover:text-ink-1",
                    )}
                  >
                    {option}
                  </button>
                );
              })}
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose} disabled={isCreating}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" disabled={isCreating || !name.trim()}>
              {isCreating ? "Creating…" : "Create"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
