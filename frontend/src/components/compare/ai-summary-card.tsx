import * as React from "react";
import type { AISuggestion } from "@/types/suggestion";
import { useGenerateSuggestions } from "@/hooks/useSuggestions";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

interface AISummaryCardProps {
  readonly runIds: ReadonlyArray<string>;
  readonly projectId: string;
}

type BadgeVariant = "default" | "secondary" | "destructive";

function riskBadgeVariant(riskLevel: AISuggestion["riskLevel"]): BadgeVariant {
  if (riskLevel === "high") return "destructive";
  if (riskLevel === "medium") return "secondary";
  return "default";
}

export function AISummaryCard({ runIds, projectId }: AISummaryCardProps): React.JSX.Element {
  const [suggestions, setSuggestions] = React.useState<ReadonlyArray<AISuggestion> | null>(null);
  const generateSuggestions = useGenerateSuggestions();

  const handleGenerate = (): void => {
    generateSuggestions.mutate(
      {
        projectId,
        request: {
          sourceRunId: runIds[0],
          notes: `Compare runs: ${runIds.join(", ")}`,
        },
      },
      {
        onSuccess: (result) => {
          setSuggestions(result);
        },
      },
    );
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm">AI Comparison Summary</CardTitle>
        <Button
          size="sm"
          variant="outline"
          onClick={handleGenerate}
          disabled={generateSuggestions.isPending}
        >
          {generateSuggestions.isPending ? "Generating…" : "Generate Summary"}
        </Button>
      </CardHeader>
      <CardContent>
        {generateSuggestions.isError && (
          <p className="text-sm text-destructive">
            Failed to generate summary. Check that an AI provider is configured in project settings.
          </p>
        )}
        {suggestions === null && !generateSuggestions.isError && (
          <p className="text-sm text-muted-foreground">
            Generate an AI-powered summary comparing the selected runs and receive optimization
            suggestions based on their metrics and configuration differences.
          </p>
        )}
        {suggestions !== null && suggestions.length === 0 && (
          <p className="text-sm text-muted-foreground">No suggestions were generated.</p>
        )}
        {suggestions !== null && suggestions.length > 0 && (
          <div className="space-y-4">
            {suggestions.map((suggestion) => (
              <div key={suggestion.id} className="space-y-2 pb-4 border-b last:border-b-0">
                <div className="flex items-center gap-2">
                  {suggestion.riskLevel != null && (
                    <Badge
                      variant={riskBadgeVariant(suggestion.riskLevel)}
                      className="text-xs shrink-0"
                    >
                      {suggestion.riskLevel} risk
                    </Badge>
                  )}
                  {suggestion.confidence != null && (
                    <span className="text-xs text-muted-foreground">
                      {Math.round(suggestion.confidence * 100)}% confidence
                    </span>
                  )}
                </div>
                <p className="text-sm">{suggestion.rationale}</p>
                {suggestion.expectedEffect != null && (
                  <p className="text-xs text-muted-foreground">
                    Expected: {suggestion.expectedEffect}
                  </p>
                )}
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
