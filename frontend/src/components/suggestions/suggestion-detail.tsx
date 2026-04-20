import * as React from "react";
import { Bookmark, MessageSquare, Sparkle, X } from "lucide-react";
import type { AISuggestion, RiskLevel } from "@/types/suggestion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { useToast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";
import { ActionCard } from "./action-card";
import { EvidenceList } from "./evidence-list";

interface SuggestionDetailProps {
  readonly suggestion: AISuggestion;
  readonly isAccepting: boolean;
  readonly isRejecting: boolean;
  readonly onAccept: (suggestionId: string) => void;
  readonly onReject: (suggestionId: string) => void;
}

const OPT_LABELS = ["A", "B", "C", "D"] as const;
// TODO(P8): action-impact bars use a static curve until a confidence field per action is returned -- remove when API exposes it
const DEFAULT_IMPACTS: ReadonlyArray<number> = [0.82, 0.64, 0.48, 0.38];

const SEVERITY_COLOR: Record<RiskLevel | "default", string> = {
  high: "var(--danger)",
  medium: "var(--warn)",
  low: "var(--success)",
  default: "var(--iris-3)",
};

function severityVariant(riskLevel: RiskLevel | null): "warn" | "danger" | "iris" | "success" {
  switch (riskLevel) {
    case "high":
      return "danger";
    case "medium":
      return "warn";
    case "low":
      return "success";
    default:
      return "iris";
  }
}

function severityBulletColor(riskLevel: RiskLevel | null): string {
  if (riskLevel === "high") return SEVERITY_COLOR.high;
  if (riskLevel === "medium") return SEVERITY_COLOR.medium;
  if (riskLevel === "low") return SEVERITY_COLOR.low;
  return SEVERITY_COLOR.default;
}

function formatPatch(key: string, suggestedValue: unknown): string {
  const rendered =
    typeof suggestedValue === "string" ? suggestedValue : JSON.stringify(suggestedValue, null, 2);
  return `${key}: ${rendered}`;
}

interface SectionLabelProps {
  readonly children: React.ReactNode;
}

function SectionLabel({ children }: SectionLabelProps): React.JSX.Element {
  return (
    <div className="mb-1.5 font-mono text-[10px] uppercase tracking-[0.1em] text-ink-3">
      {children}
    </div>
  );
}

export function SuggestionDetail({
  suggestion,
  isAccepting,
  isRejecting,
  onAccept,
  onReject,
}: SuggestionDetailProps): React.JSX.Element {
  const { toast } = useToast();
  const { id, status, rationale, expectedEffect, tradeoffs, riskLevel, configDiff, evidence } =
    suggestion;

  const canAct = status === "pending";
  const variant = severityVariant(riskLevel);
  const bulletColor = severityBulletColor(riskLevel);

  const actions = React.useMemo(() => {
    return Object.entries(configDiff).map(([key, change], index) => ({
      key,
      optLabel: OPT_LABELS[index] ?? "·",
      impact: DEFAULT_IMPACTS[index] ?? 0.4,
      label: key,
      patch: formatPatch(key, change.suggested),
    }));
  }, [configDiff]);

  const handlePreview = (actionKey: string): void => {
    toast({ title: "Previewed", description: `Previewing change to ${actionKey}.` });
  };

  return (
    <Card className="iris-glow">
      <CardHeader className="py-3.5">
        <div className="flex flex-col gap-1">
          <CardTitle className="flex items-center gap-2">
            <span
              aria-hidden="true"
              className="h-2 w-2 rounded-full"
              style={{ background: bulletColor }}
            />
            <span className="truncate text-[13px]">{rationale || "Suggestion"}</span>
          </CardTitle>
          <div className="flex items-center gap-2">
            <Badge variant={variant} dot={false}>
              {(riskLevel ?? "iris").toUpperCase()}
            </Badge>
            <span className="font-mono text-[10.5px] text-ink-3">status · {status}</span>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            aria-label="Bookmark suggestion for later"
            onClick={() => toast({ title: "Bookmarked", description: "Marked for later review." })}
          >
            <Bookmark className="h-3.5 w-3.5" aria-hidden="true" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            aria-label="Reject suggestion"
            disabled={!canAct || isRejecting}
            onClick={() => onReject(id)}
          >
            <X className="h-3.5 w-3.5" aria-hidden="true" />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <section>
          <SectionLabel>What happened</SectionLabel>
          <p className="text-[13.5px] leading-[1.55] text-ink-1">{rationale}</p>
        </section>

        {expectedEffect ? (
          <section>
            <SectionLabel>Why it matters</SectionLabel>
            <p className="text-[13.5px] leading-[1.55] text-ink-1">{expectedEffect}</p>
          </section>
        ) : null}

        {tradeoffs ? (
          <section>
            <SectionLabel>Tradeoffs</SectionLabel>
            <p className="text-[13.5px] leading-[1.55] text-ink-2">{tradeoffs}</p>
          </section>
        ) : null}

        <section>
          <SectionLabel>Recommended actions</SectionLabel>
          {actions.length === 0 ? (
            <p className="font-mono text-[11px] text-ink-3">No config changes proposed.</p>
          ) : (
            <div className="flex flex-col gap-2.5">
              {actions.map((entry) => (
                <ActionCard
                  key={entry.key}
                  optLabel={entry.optLabel}
                  impact={entry.impact}
                  label={entry.label}
                  patch={entry.patch}
                  isApplying={isAccepting}
                  canAct={canAct}
                  onPreview={() => handlePreview(entry.key)}
                  onApply={() => onAccept(id)}
                />
              ))}
            </div>
          )}
        </section>

        {evidence.length > 0 ? (
          <section>
            <SectionLabel>Evidence</SectionLabel>
            <EvidenceList evidence={evidence} />
          </section>
        ) : null}
      </CardContent>
      <CardFooter>
        <span className={cn("font-mono text-[10px] uppercase tracking-[0.1em] text-ink-4")}>
          claude-sonnet-4-5 · offline analysis
        </span>
        <Button
          variant="outline"
          size="sm"
          onClick={() =>
            toast({
              title: "Ask Claude",
              description: "Conversational follow-up is not yet wired.",
            })
          }
        >
          <MessageSquare aria-hidden="true" />
          Ask Claude
        </Button>
      </CardFooter>
    </Card>
  );
}

export function SuggestionEmptyHint(): React.JSX.Element {
  return (
    <div className="flex h-full items-center justify-center gap-2 font-mono text-[11px] text-ink-3">
      <Sparkle className="h-3.5 w-3.5" aria-hidden="true" />
      Select a suggestion to view details.
    </div>
  );
}
