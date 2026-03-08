import type { AISuggestion } from "@/types/suggestion";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { ConfidenceBadge, RiskBadge, ProviderBadge } from "./suggestion-badges";
import { ConfigDiffView } from "./config-diff-view";
import { EvidenceList } from "./evidence-list";

interface SuggestionDetailProps {
  readonly suggestion: AISuggestion;
  readonly isAccepting: boolean;
  readonly isRejecting: boolean;
  readonly onAccept: (suggestionId: string) => void;
  readonly onReject: (suggestionId: string) => void;
}

interface RationaleTextProps {
  readonly rationale: string;
}

function RationaleText({ rationale }: RationaleTextProps): React.JSX.Element {
  return <p className="text-sm leading-relaxed">{rationale}</p>;
}

interface ExpectedEffectTextProps {
  readonly expectedEffect: string | null;
}

function ExpectedEffectText({ expectedEffect }: ExpectedEffectTextProps): React.JSX.Element {
  if (!expectedEffect) return <></>;
  return <p className="text-sm leading-relaxed text-muted-foreground">{expectedEffect}</p>;
}

interface TradeoffsTextProps {
  readonly tradeoffs: string | null;
}

function TradeoffsText({ tradeoffs }: TradeoffsTextProps): React.JSX.Element {
  if (!tradeoffs) return <></>;
  return <p className="text-sm leading-relaxed text-muted-foreground">{tradeoffs}</p>;
}

const isPending = (suggestion: AISuggestion): boolean => suggestion.status === "pending";

export function SuggestionDetail({
  suggestion,
  isAccepting,
  isRejecting,
  onAccept,
  onReject,
}: SuggestionDetailProps): React.JSX.Element {
  const {
    id,
    status,
    rationale,
    expectedEffect,
    tradeoffs,
    confidence,
    riskLevel,
    provider,
    configDiff,
    evidence,
    appliedConfigVersionId,
  } = suggestion;
  const canAct = isPending(suggestion);

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      <div className="p-4 border-b space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <ProviderBadge provider={provider} />
          <RiskBadge riskLevel={riskLevel} />
          <ConfidenceBadge confidence={confidence} />
          <span className="ml-auto text-xs text-muted-foreground capitalize">{status}</span>
        </div>

        {canAct && (
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              onClick={() => onAccept(id)}
              disabled={isAccepting || isRejecting}
              aria-label="Accept suggestion and create config version"
            >
              {isAccepting ? "Accepting…" : "Accept"}
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => onReject(id)}
              disabled={isAccepting || isRejecting}
              aria-label="Reject suggestion"
            >
              {isRejecting ? "Rejecting…" : "Reject"}
            </Button>
          </div>
        )}

        {status === "accepted" && appliedConfigVersionId && (
          <p className="text-xs text-green-700">
            Applied as config version: <span className="font-mono">{appliedConfigVersionId}</span>
          </p>
        )}
      </div>

      <div className="flex-1 p-4 space-y-5">
        <section>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
            Rationale
          </h3>
          <RationaleText rationale={rationale} />
        </section>

        <Separator />

        <section>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
            Config Changes
          </h3>
          <ConfigDiffView configDiff={configDiff} />
        </section>

        {evidence.length > 0 && (
          <>
            <Separator />
            <section>
              <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
                Evidence
              </h3>
              <EvidenceList evidence={evidence} />
            </section>
          </>
        )}

        {expectedEffect && (
          <>
            <Separator />
            <section>
              <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
                Expected Effect
              </h3>
              <ExpectedEffectText expectedEffect={expectedEffect} />
            </section>
          </>
        )}

        {tradeoffs && (
          <>
            <Separator />
            <section>
              <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
                Tradeoffs
              </h3>
              <TradeoffsText tradeoffs={tradeoffs} />
            </section>
          </>
        )}
      </div>
    </div>
  );
}
