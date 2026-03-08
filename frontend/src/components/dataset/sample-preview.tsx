import * as React from "react";
import type { DatasetSample } from "@/types/dataset";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ScrollArea } from "@/components/ui/scroll-area";

interface SamplePreviewProps {
  readonly samples: ReadonlyArray<DatasetSample>;
  readonly detectedFields: ReadonlyArray<string>;
}

function truncate(value: unknown, maxLength = 120): string {
  const str = typeof value === "string" ? value : JSON.stringify(value);
  return str.length > maxLength ? str.slice(0, maxLength) + "…" : str;
}

export function SamplePreview({ samples, detectedFields }: SamplePreviewProps): React.JSX.Element {
  if (samples.length === 0) {
    return (
      <div className="flex items-center justify-center h-24 text-sm text-muted-foreground border rounded-md">
        No samples available.
      </div>
    );
  }

  const columns = detectedFields.length > 0 ? detectedFields : Object.keys(samples[0]?.row ?? {});

  return (
    <ScrollArea className="h-64 rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-12 text-xs">#</TableHead>
            {columns.map((col) => (
              <TableHead key={col} className="text-xs">
                {col}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {samples.map(({ index, row }) => (
            <TableRow key={index}>
              <TableCell className="text-xs text-muted-foreground">{index}</TableCell>
              {columns.map((col) => (
                <TableCell key={col} className="text-xs max-w-xs">
                  <span
                    title={
                      typeof row[col] === "string" ? (row[col] as string) : JSON.stringify(row[col])
                    }
                  >
                    {truncate(row[col])}
                  </span>
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </ScrollArea>
  );
}
