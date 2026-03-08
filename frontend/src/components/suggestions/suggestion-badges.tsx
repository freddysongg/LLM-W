import { Badge } from "@/components/ui/badge";
import type { RiskLevel, SuggestionProvider } from "@/types/suggestion";

interface ConfidenceBadgeProps {
  readonly confidence: number | null;
}

export function ConfidenceBadge({ confidence }: ConfidenceBadgeProps): React.JSX.Element {
  if (confidence === null) {
    return <Badge variant="outline">Unknown confidence</Badge>;
  }
  const pct = Math.round(confidence * 100);
  const variant = pct >= 70 ? "default" : pct >= 40 ? "secondary" : "outline";
  return <Badge variant={variant}>{pct}% confidence</Badge>;
}

interface RiskBadgeProps {
  readonly riskLevel: RiskLevel | null;
}

const RISK_CLASSES: Record<RiskLevel, string> = {
  low: "bg-green-100 text-green-800 border-green-200",
  medium: "bg-yellow-100 text-yellow-800 border-yellow-200",
  high: "bg-red-100 text-red-800 border-red-200",
};

export function RiskBadge({ riskLevel }: RiskBadgeProps): React.JSX.Element {
  if (!riskLevel) return <></>;
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${RISK_CLASSES[riskLevel]}`}
    >
      {riskLevel} risk
    </span>
  );
}

interface ProviderBadgeProps {
  readonly provider: SuggestionProvider;
}

const PROVIDER_LABELS: Record<SuggestionProvider, string> = {
  anthropic: "Claude",
  openai_compatible: "OpenAI",
  rule_engine: "Rule-based",
};

export function ProviderBadge({ provider }: ProviderBadgeProps): React.JSX.Element {
  return <Badge variant="outline">{PROVIDER_LABELS[provider]}</Badge>;
}
