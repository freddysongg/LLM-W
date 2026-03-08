import * as React from "react";
import type { ModelProfile } from "@/types/model";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface CurrentModelCardProps {
  readonly profile: ModelProfile | undefined;
  readonly isLoading: boolean;
}

function formatParamCount(count: number): string {
  if (count >= 1_000_000_000) return `${(count / 1_000_000_000).toFixed(1)}B`;
  if (count >= 1_000_000) return `${(count / 1_000_000).toFixed(1)}M`;
  if (count >= 1_000) return `${(count / 1_000).toFixed(1)}K`;
  return String(count);
}

export function CurrentModelCard({ profile, isLoading }: CurrentModelCardProps): React.JSX.Element {
  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Active Model</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">Loading...</CardContent>
      </Card>
    );
  }

  if (!profile) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Active Model</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">No model resolved.</CardContent>
      </Card>
    );
  }

  const { model_id, family, architecture_name, total_parameters, trainable_parameters, source } =
    profile;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Active Model</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <div className="font-mono text-xs truncate" title={model_id}>
          {model_id}
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <Badge variant="outline" className="text-xs">
            {family}
          </Badge>
          <Badge variant="secondary" className="text-xs">
            {source}
          </Badge>
        </div>
        <div className="text-xs text-muted-foreground">{architecture_name}</div>
        <div className="text-xs text-muted-foreground">
          {formatParamCount(total_parameters)} params &mdash;{" "}
          {formatParamCount(trainable_parameters)} trainable
        </div>
      </CardContent>
    </Card>
  );
}
