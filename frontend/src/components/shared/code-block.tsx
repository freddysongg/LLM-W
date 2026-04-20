import * as React from "react";
import { Check, Copy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";

export interface CodeBlockProps {
  readonly code: string;
  readonly language?: string;
  readonly className?: string;
  readonly copyable?: boolean;
}

const COPY_RESET_MS = 1500;

export function CodeBlock({
  code,
  language,
  className,
  copyable = true,
}: CodeBlockProps): React.JSX.Element {
  const [isCopied, setIsCopied] = React.useState<boolean>(false);
  const { toast } = useToast();

  React.useEffect(() => {
    if (!isCopied) return;
    const id = setTimeout(() => setIsCopied(false), COPY_RESET_MS);
    return () => clearTimeout(id);
  }, [isCopied]);

  const handleCopy = async (): Promise<void> => {
    try {
      await navigator.clipboard.writeText(code);
      setIsCopied(true);
      toast({ title: "Copied", description: "Snippet copied to clipboard." });
    } catch (error) {
      toast({
        title: "Copy failed",
        description: error instanceof Error ? error.message : "Clipboard access denied.",
        variant: "destructive",
      });
    }
  };

  return (
    <div className={cn("relative", className)}>
      <pre
        className={cn(
          "overflow-x-auto rounded-md border border-hairline bg-surface-2 p-3",
          "font-mono text-[12px] leading-[1.6] text-ink-1",
        )}
      >
        <code data-language={language}>{code}</code>
      </pre>
      {copyable ? (
        <Button
          type="button"
          size="icon"
          variant="ghost"
          className="absolute right-2 top-2 h-7 w-7 text-ink-3 hover:text-ink-1"
          onClick={() => {
            void handleCopy();
          }}
          aria-label={isCopied ? "Copied" : "Copy code"}
        >
          {isCopied ? (
            <Check className="size-3.5" aria-hidden="true" />
          ) : (
            <Copy className="size-3.5" aria-hidden="true" />
          )}
        </Button>
      ) : null}
    </div>
  );
}
