import * as React from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import type { ModelProfile } from "@/types/model";

interface TokenizerInfoProps {
  readonly profile: ModelProfile;
}

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

export function TokenizerInfo({ profile }: TokenizerInfoProps): React.JSX.Element {
  const { vocabulary_size, context_length, torch_dtype } = profile;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium">Tokenizer</CardTitle>
      </CardHeader>
      <CardContent>
        {vocabulary_size !== null && (
          <StatRow label="Vocab Size" value={vocabulary_size.toLocaleString()} />
        )}
        {context_length !== null && (
          <StatRow label="Context Length" value={context_length.toLocaleString()} />
        )}
        <StatRow label="Dtype" value={torch_dtype} />
      </CardContent>
    </Card>
  );
}
