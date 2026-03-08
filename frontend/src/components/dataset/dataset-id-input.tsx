import * as React from "react";
import type { DatasetSource } from "@/types/config";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";

interface DatasetIdInputProps {
  readonly source: DatasetSource;
  readonly value: string;
  readonly onChange: (value: string) => void;
}

const PLACEHOLDERS: Record<DatasetSource, string> = {
  huggingface: "e.g. tatsu-lab/alpaca",
  local_jsonl: "e.g. /data/train.jsonl",
  local_csv: "e.g. /data/train.csv",
  custom: "e.g. /data/train.jsonl",
};

const LABELS: Record<DatasetSource, string> = {
  huggingface: "Dataset ID",
  local_jsonl: "File Path",
  local_csv: "File Path",
  custom: "File Path",
};

export function DatasetIdInput({
  source,
  value,
  onChange,
}: DatasetIdInputProps): React.JSX.Element {
  return (
    <div className="space-y-2">
      <Label htmlFor="dataset-id">{LABELS[source]}</Label>
      <Input
        id="dataset-id"
        type="text"
        placeholder={PLACEHOLDERS[source]}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}
