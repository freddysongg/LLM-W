import * as React from "react";
import type { JudgeVerdict } from "@/types/eval";
import { Badge } from "@/components/ui/badge";

interface JudgeVerdictBadgeProps {
  readonly verdict: JudgeVerdict;
}

type BadgeVariant = "default" | "secondary" | "destructive" | "outline";

function verdictVariant(verdict: JudgeVerdict): BadgeVariant {
  switch (verdict) {
    case "pass":
      return "secondary";
    case "fail":
      return "destructive";
    default: {
      const exhaustive: never = verdict;
      return exhaustive;
    }
  }
}

export function JudgeVerdictBadge({ verdict }: JudgeVerdictBadgeProps): React.JSX.Element {
  return <Badge variant={verdictVariant(verdict)}>{verdict}</Badge>;
}
