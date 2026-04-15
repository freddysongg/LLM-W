import * as React from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";

interface CotExpansionProps {
  readonly title: string;
  readonly reasoning: string;
  readonly defaultOpen?: boolean;
}

export function CotExpansion({
  title,
  reasoning,
  defaultOpen = false,
}: CotExpansionProps): React.JSX.Element {
  const [isOpen, setIsOpen] = React.useState<boolean>(defaultOpen);

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <CollapsibleTrigger asChild>
        <button
          type="button"
          className={cn(
            "flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors",
          )}
        >
          {isOpen ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
          <span>{title}</span>
        </button>
      </CollapsibleTrigger>
      <CollapsibleContent className="mt-2">
        <pre className="text-xs text-muted-foreground bg-muted rounded px-3 py-2 whitespace-pre-wrap font-mono overflow-x-auto">
          {reasoning}
        </pre>
      </CollapsibleContent>
    </Collapsible>
  );
}
