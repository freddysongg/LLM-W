import * as React from "react";
import type { ModelProfile } from "@/types/model";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { KVList } from "@/components/shared/kv-list";
import type { KVRow } from "@/components/shared/kv-list";

interface CurrentModelCardProps {
  readonly profile: ModelProfile | undefined;
  readonly isLoading: boolean;
}

function formatParamCount(count: number): string {
  if (count >= 1_000_000_000) return `${(count / 1_000_000_000).toFixed(2)}B`;
  if (count >= 1_000_000) return `${(count / 1_000_000).toFixed(1)}M`;
  if (count >= 1_000) return `${(count / 1_000).toFixed(1)}K`;
  return String(count);
}

function formatContextLength(length: number | null): string {
  if (length === null) return "—";
  return `${length.toLocaleString()} tok`;
}

function sourceBadgeLabel(source: ModelProfile["source"]): string {
  switch (source) {
    case "huggingface":
      return "HF";
    case "local":
      return "local";
    default: {
      const _exhaustive: never = source;
      return _exhaustive;
    }
  }
}

function buildRows(profile: ModelProfile): ReadonlyArray<KVRow> {
  const { model_id, total_parameters, torch_dtype, context_length, architecture_name } = profile;
  return [
    { key: "Model", value: model_id },
    { key: "Params", value: formatParamCount(total_parameters) },
    { key: "Dtype", value: torch_dtype },
    { key: "Context", value: formatContextLength(context_length) },
    { key: "Architecture", value: architecture_name },
  ];
}

export function CurrentModelCard({ profile, isLoading }: CurrentModelCardProps): React.JSX.Element {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Current model</CardTitle>
        {profile ? (
          <Badge variant="iris" dot={false}>
            {sourceBadgeLabel(profile.source)}
          </Badge>
        ) : null}
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="font-mono text-[11px] text-ink-3">Loading…</div>
        ) : profile ? (
          <KVList rows={buildRows(profile)} dense />
        ) : (
          <div className="font-mono text-[11px] text-ink-3">No model resolved.</div>
        )}
      </CardContent>
    </Card>
  );
}
