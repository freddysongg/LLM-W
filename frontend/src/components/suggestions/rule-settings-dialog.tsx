import * as React from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Switch } from "@/components/ui/switch";
import { AI_RULE_ORDER, type AIRuleName, type AIRuleSettings } from "@/types/ai-rule-settings";

interface RuleSettingsDialogProps {
  readonly isOpen: boolean;
  readonly initialSettings: AIRuleSettings | undefined;
  readonly isPending: boolean;
  readonly onOpenChange: (open: boolean) => void;
  readonly onSave: (settings: AIRuleSettings) => void;
}

function withToggle({
  settings,
  rule,
  enabled,
}: {
  settings: AIRuleSettings;
  rule: AIRuleName;
  enabled: boolean;
}): AIRuleSettings {
  return { ...settings, [rule]: { enabled } };
}

export function RuleSettingsDialog({
  isOpen,
  initialSettings,
  isPending,
  onOpenChange,
  onSave,
}: RuleSettingsDialogProps): React.JSX.Element {
  const [draft, setDraft] = React.useState<AIRuleSettings | null>(null);

  React.useEffect(() => {
    if (isOpen && initialSettings) {
      setDraft(initialSettings);
    } else if (!isOpen) {
      setDraft(null);
    }
  }, [isOpen, initialSettings]);

  const handleSave = (): void => {
    if (!draft) return;
    onSave(draft);
  };

  const activeDraft = draft ?? initialSettings;

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-[640px]">
        <DialogHeader>
          <DialogTitle>Suggestion rule settings</DialogTitle>
          <DialogDescription>
            Toggle which rule-engine signals surface as suggestions. Disabled rules are skipped on
            the next Re-scan and persist per project.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-2 px-6 py-4">
          {AI_RULE_ORDER.map(({ name, title, description }) => {
            const isEnabled = activeDraft?.[name]?.enabled ?? true;
            return (
              <label
                key={name}
                className="flex items-start justify-between gap-4 rounded-[10px] border border-hairline bg-surface-2 px-3 py-2.5"
              >
                <div className="min-w-0 flex-1">
                  <div className="font-mono text-[12px] font-medium text-ink-1">{title}</div>
                  <div className="mt-0.5 font-mono text-[10.5px] text-ink-3">{description}</div>
                </div>
                <Switch
                  checked={isEnabled}
                  disabled={isPending || !activeDraft}
                  onCheckedChange={(checked) => {
                    if (!activeDraft) return;
                    setDraft(withToggle({ settings: activeDraft, rule: name, enabled: checked }));
                  }}
                  aria-label={`${title} ${isEnabled ? "enabled" : "disabled"}`}
                />
              </label>
            );
          })}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isPending}>
            Cancel
          </Button>
          <Button
            variant="primary"
            onClick={handleSave}
            disabled={isPending || !draft || !activeDraft}
          >
            {isPending ? "Saving…" : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
