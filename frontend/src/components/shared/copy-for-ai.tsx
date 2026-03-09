import * as React from "react";
import { ClipboardCopy, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";

interface CopyForAIProps {
  readonly buildPrompt: () => string;
  readonly disabled?: boolean;
}

export function CopyForAI({ buildPrompt, disabled = false }: CopyForAIProps): React.JSX.Element {
  const [isCopied, setIsCopied] = React.useState(false);
  const { toast } = useToast();

  const handleClick = (): void => {
    const prompt = buildPrompt();
    navigator.clipboard.writeText(prompt).then(() => {
      setIsCopied(true);
      toast({
        title: "Copied for AI",
        description: "Paste into Claude, GPT, or any AI assistant.",
      });
      const timeout = setTimeout(() => {
        setIsCopied(false);
      }, 1500);
      return () => clearTimeout(timeout);
    });
  };

  return (
    <Button
      variant="ghost"
      size="icon"
      className="h-7 w-7 text-muted-foreground hover:text-foreground"
      disabled={disabled}
      onClick={handleClick}
      title="Copy for AI"
    >
      {isCopied ? <Check className="h-4 w-4" /> : <ClipboardCopy className="h-4 w-4" />}
    </Button>
  );
}
