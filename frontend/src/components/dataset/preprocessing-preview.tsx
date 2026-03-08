import * as React from "react";
import type { DatasetFormat } from "@/types/config";
import type { PreviewTransformResponse } from "@/types/dataset";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface PreprocessingPreviewProps {
  readonly format: DatasetFormat;
  readonly isPending: boolean;
  readonly response: PreviewTransformResponse | null;
  readonly onPreview: () => void;
}

export function PreprocessingPreview({
  format,
  isPending,
  response,
  onPreview,
}: PreprocessingPreviewProps): React.JSX.Element {
  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm">Preprocessing Preview</CardTitle>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onPreview}
            disabled={isPending}
          >
            {isPending ? "Loading…" : "Preview Transform"}
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {response === null && !isPending && (
          <p className="text-xs text-muted-foreground">
            Click Preview Transform to see how samples will look after format transformation.
          </p>
        )}
        {isPending && (
          <p className="text-xs text-muted-foreground">Applying transform to samples…</p>
        )}
        {response !== null && !isPending && (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">Format applied:</span>
              <Badge variant="secondary" className="text-xs">
                {response.formatApplied}
              </Badge>
              {response.truncated && (
                <Badge variant="outline" className="text-xs text-yellow-600">
                  truncated
                </Badge>
              )}
            </div>
            <ScrollArea className="h-48 rounded-md border">
              <div className="p-3 space-y-2">
                {response.samples.map((sample, i) => (
                  <div
                    key={i}
                    className="rounded-sm bg-muted p-2 text-xs font-mono whitespace-pre-wrap break-all"
                  >
                    {JSON.stringify(sample, null, 2)}
                  </div>
                ))}
              </div>
            </ScrollArea>
            <p className="text-xs text-muted-foreground">
              Showing {response.samples.length} sample{response.samples.length !== 1 ? "s" : ""}{" "}
              after {format} format transformation.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
