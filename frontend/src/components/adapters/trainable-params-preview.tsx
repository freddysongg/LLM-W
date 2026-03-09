import * as React from "react";
import type { AdaptersConfig } from "@/types/config";
import { useModelProfile } from "@/hooks/useModelProfile";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";

interface TrainableParamsPreviewProps {
  readonly adapters: AdaptersConfig;
  readonly projectId: string;
}

function formatParamCount(count: number): string {
  if (count >= 1_000_000_000) return `${(count / 1_000_000_000).toFixed(2)}B`;
  if (count >= 1_000_000) return `${(count / 1_000_000).toFixed(2)}M`;
  if (count >= 1_000) return `${(count / 1_000).toFixed(1)}K`;
  return String(count);
}

export function TrainableParamsPreview({
  adapters,
  projectId,
}: TrainableParamsPreviewProps): React.JSX.Element {
  const { data: modelProfile, isLoading } = useModelProfile({ projectId });

  if (!adapters.enabled) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Parameter Preview</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Enable adapters to see trainable parameter counts.
          </p>
        </CardContent>
      </Card>
    );
  }

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Parameter Preview</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">Loading model profile…</p>
        </CardContent>
      </Card>
    );
  }

  if (!modelProfile) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Parameter Preview</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Resolve a model first to see trainable parameter counts.
          </p>
        </CardContent>
      </Card>
    );
  }

  const { total_parameters, trainable_parameters } = modelProfile;
  const trainablePct = total_parameters > 0 ? (trainable_parameters / total_parameters) * 100 : 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Parameter Preview</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="space-y-1">
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Trainable</span>
            <span className="font-mono font-medium">{formatParamCount(trainable_parameters)}</span>
          </div>
          <Progress value={trainablePct} className="h-1.5" />
          <p className="text-xs text-muted-foreground text-right">
            {trainablePct.toFixed(2)}% of {formatParamCount(total_parameters)} total
          </p>
        </div>
        <div className="text-xs text-muted-foreground space-y-1 pt-1 border-t">
          <div className="flex justify-between">
            <span>Rank (r)</span>
            <span className="font-mono">{adapters.rank}</span>
          </div>
          <div className="flex justify-between">
            <span>Target modules</span>
            <span className="font-mono truncate ml-2 text-right">
              {(adapters.targetModules ?? []).length > 0
                ? (adapters.targetModules ?? []).join(", ")
                : "none selected"}
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
