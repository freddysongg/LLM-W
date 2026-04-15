import * as React from "react";
import { Download } from "lucide-react";
import type { EvalRunDetail } from "@/types/eval";
import { Button } from "@/components/ui/button";
import { downloadEvalRunAsJson } from "@/api/eval";

interface EvalExportButtonProps {
  readonly evalRunDetail: EvalRunDetail;
}

export function EvalExportButton({ evalRunDetail }: EvalExportButtonProps): React.JSX.Element {
  const handleExportClick = (): void => {
    downloadEvalRunAsJson({ evalRunDetail });
  };

  return (
    <Button variant="outline" size="sm" onClick={handleExportClick} className="gap-1.5">
      <Download className="h-3.5 w-3.5" />
      Export JSON
    </Button>
  );
}
