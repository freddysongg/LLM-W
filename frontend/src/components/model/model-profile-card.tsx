import * as React from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import type { ModelProfile } from "@/types/model";

interface ModelProfileCardProps {
  readonly profile: ModelProfile;
}

function formatParamCount(count: number): string {
  if (count >= 1_000_000_000) return `${(count / 1_000_000_000).toFixed(1)}B`;
  if (count >= 1_000_000) return `${(count / 1_000_000).toFixed(1)}M`;
  if (count >= 1_000) return `${(count / 1_000).toFixed(1)}K`;
  return String(count);
}

const FAMILY_LABELS: Record<string, string> = {
  causal_lm: "Causal LM",
  seq2seq: "Seq2Seq",
  encoder_only: "Encoder-only",
};

interface StatRowProps {
  readonly label: string;
  readonly value: string;
}

function StatRow({ label, value }: StatRowProps): React.JSX.Element {
  return (
    <div className="flex justify-between items-center py-1.5 border-b last:border-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-mono font-medium">{value}</span>
    </div>
  );
}

export function ModelProfileCard({ profile }: ModelProfileCardProps): React.JSX.Element {
  const { architecture_name, family, total_parameters, vocabulary_size } = profile;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium">Model Profile</CardTitle>
      </CardHeader>
      <CardContent>
        <StatRow label="Architecture" value={architecture_name} />
        <StatRow label="Family" value={FAMILY_LABELS[family] ?? family} />
        <StatRow label="Parameters" value={formatParamCount(total_parameters)} />
        {vocabulary_size !== null && (
          <StatRow label="Vocab Size" value={vocabulary_size.toLocaleString()} />
        )}
      </CardContent>
    </Card>
  );
}
