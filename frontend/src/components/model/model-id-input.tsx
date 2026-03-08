import * as React from "react";
import { Input } from "@/components/ui/input";
import type { ModelSource } from "@/types/model";

interface ModelIdInputProps {
  readonly source: ModelSource;
  readonly value: string;
  readonly onChange: (value: string) => void;
  readonly isDisabled?: boolean;
}

const PLACEHOLDER: Record<ModelSource, string> = {
  huggingface: "e.g. meta-llama/Meta-Llama-3-8B",
  local: "e.g. /models/my-fine-tuned-model",
};

export function ModelIdInput({
  source,
  value,
  onChange,
  isDisabled = false,
}: ModelIdInputProps): React.JSX.Element {
  return (
    <Input
      type="text"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={PLACEHOLDER[source]}
      disabled={isDisabled}
      className="font-mono text-sm"
    />
  );
}
