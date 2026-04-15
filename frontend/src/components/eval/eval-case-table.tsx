import * as React from "react";
import type { EvalCall, EvalCase } from "@/types/eval";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { JudgeVerdictBadge } from "./judge-verdict-badge";

interface EvalCaseTableProps {
  readonly cases: ReadonlyArray<EvalCase>;
  readonly callsByCaseId: ReadonlyMap<string, ReadonlyArray<EvalCall>>;
  readonly selectedCaseId: string | null;
  readonly onSelectCase: (caseId: string) => void;
}

const PROMPT_PREVIEW_LENGTH = 80;
const OUTPUT_PREVIEW_LENGTH = 80;

function previewText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength).trimEnd()}…`;
}

function formatUsd(amount: number): string {
  return `$${amount.toFixed(4)}`;
}

function sumCallCost(calls: ReadonlyArray<EvalCall>): number {
  return calls.reduce<number>((total, call) => total + call.costUsd, 0);
}

export function EvalCaseTable({
  cases,
  callsByCaseId,
  selectedCaseId,
  onSelectCase,
}: EvalCaseTableProps): React.JSX.Element {
  if (cases.length === 0) {
    return (
      <div className="py-12 flex flex-col items-center gap-3 text-sm text-muted-foreground">
        <span>No cases recorded yet.</span>
      </div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Prompt</TableHead>
          <TableHead>Output</TableHead>
          <TableHead>Verdicts</TableHead>
          <TableHead className="text-right">Cost</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {cases.map((evalCase) => {
          const { id, caseInput } = evalCase;
          const caseCalls = callsByCaseId.get(id) ?? [];
          return (
            <TableRow
              key={id}
              onClick={() => onSelectCase(id)}
              className={`cursor-pointer ${selectedCaseId === id ? "bg-accent" : "hover:bg-muted/50"}`}
            >
              <TableCell className="max-w-[280px] text-sm">
                {previewText(caseInput.prompt, PROMPT_PREVIEW_LENGTH)}
              </TableCell>
              <TableCell className="max-w-[280px] text-sm text-muted-foreground">
                {previewText(caseInput.output, OUTPUT_PREVIEW_LENGTH)}
              </TableCell>
              <TableCell>
                <div className="flex flex-wrap gap-1">
                  {caseCalls.length === 0 ? (
                    <span className="text-xs text-muted-foreground">pending…</span>
                  ) : (
                    caseCalls.map((call) => (
                      <JudgeVerdictBadge key={call.id} verdict={call.verdict} />
                    ))
                  )}
                </div>
              </TableCell>
              <TableCell className="text-right text-xs text-muted-foreground">
                {formatUsd(sumCallCost(caseCalls))}
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
