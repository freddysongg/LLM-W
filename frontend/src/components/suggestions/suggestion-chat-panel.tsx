import * as React from "react";
import { Send, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useSendSuggestionChatMessage, useSuggestionChat } from "@/hooks/useSuggestionChat";
import { useToast } from "@/hooks/use-toast";
import { describeApiError } from "@/lib/api-error";
import { cn } from "@/lib/utils";

interface SuggestionChatPanelProps {
  readonly projectId: string;
  readonly suggestionId: string;
  readonly onClose: () => void;
}

export function SuggestionChatPanel({
  projectId,
  suggestionId,
  onClose,
}: SuggestionChatPanelProps): React.JSX.Element {
  const [draft, setDraft] = React.useState<string>("");
  const { toast } = useToast();
  const {
    data: messages = [],
    isLoading,
    isError,
  } = useSuggestionChat({ projectId, suggestionId, enabled: true });
  const sendMessage = useSendSuggestionChatMessage({ projectId, suggestionId });

  const trimmedDraft = draft.trim();
  const isSendDisabled = sendMessage.isPending || trimmedDraft.length === 0;

  const handleSend = (): void => {
    if (isSendDisabled) return;
    sendMessage.mutate(trimmedDraft, {
      onSuccess: () => {
        setDraft("");
      },
      onError: (cause) => {
        toast({
          title: "Ask Claude failed",
          description: describeApiError({
            cause,
            fallback: "The AI provider call did not complete.",
          }),
          variant: "destructive",
        });
      },
    });
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>): void => {
    if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
      event.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col gap-3 border-t border-hairline px-5 py-4">
      <div className="flex items-center justify-between">
        <h3 className="font-mono text-[11px] uppercase tracking-[0.08em] text-ink-3">
          Ask Claude about this suggestion
        </h3>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7"
          onClick={onClose}
          aria-label="Close chat"
        >
          <X className="h-3.5 w-3.5" aria-hidden="true" />
        </Button>
      </div>

      <div className="flex max-h-[280px] flex-col gap-2 overflow-y-auto rounded-[10px] border border-hairline bg-surface-2 p-3">
        {isLoading ? (
          <p className="font-mono text-[11px] text-ink-3">Loading conversation…</p>
        ) : isError ? (
          <p className="font-mono text-[11px] text-[color:var(--danger)]">
            Could not load chat history.
          </p>
        ) : messages.length === 0 ? (
          <p className="font-mono text-[11px] text-ink-3">
            Ask why this suggestion fired, what changes if you accept it, or how it interacts with
            your current config.
          </p>
        ) : (
          messages.map(({ id, role, content }) => (
            <div
              key={id}
              className={cn(
                "rounded-[8px] px-3 py-2 font-mono text-[12px] leading-[1.45]",
                role === "user"
                  ? "self-end bg-ink-1 text-[color:var(--surface)]"
                  : "self-start bg-surface text-ink-1",
              )}
            >
              {content}
            </div>
          ))
        )}
      </div>

      <div className="flex items-end gap-2">
        <textarea
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Why does this trigger when train loss is dropping?"
          rows={2}
          disabled={sendMessage.isPending}
          className="min-h-[44px] flex-1 resize-none rounded-[10px] border border-hairline bg-surface px-3 py-2 font-mono text-[12px] text-ink-1 placeholder:text-ink-3 focus:outline-none focus:ring-2 focus:ring-iris-3 disabled:opacity-60"
        />
        <Button variant="primary" size="sm" onClick={handleSend} disabled={isSendDisabled}>
          <Send className="size-3" aria-hidden="true" />
          {sendMessage.isPending ? "Sending…" : "Send"}
        </Button>
      </div>
    </div>
  );
}
