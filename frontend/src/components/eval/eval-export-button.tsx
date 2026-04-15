import * as React from "react";
import { Download } from "lucide-react";
import type { EvalRunDetail } from "@/types/eval";
import { Button } from "@/components/ui/button";

interface EvalExportButtonProps {
  readonly evalRunDetail: EvalRunDetail;
}

const JSON_INDENT_SPACES = 2;
const DOWNLOAD_MIME_TYPE = "application/json";

function triggerJsonDownload({
  filename,
  jsonPayload,
}: {
  filename: string;
  jsonPayload: string;
}): void {
  const blob = new Blob([jsonPayload], { type: DOWNLOAD_MIME_TYPE });
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(objectUrl);
}

export function EvalExportButton({ evalRunDetail }: EvalExportButtonProps): React.JSX.Element {
  const handleExportClick = (): void => {
    const jsonPayload = JSON.stringify(evalRunDetail, null, JSON_INDENT_SPACES);
    const filename = `eval-run-${evalRunDetail.run.id}.json`;
    triggerJsonDownload({ filename, jsonPayload });
  };

  return (
    <Button variant="outline" size="sm" onClick={handleExportClick} className="gap-1.5">
      <Download className="h-3.5 w-3.5" />
      Export JSON
    </Button>
  );
}
