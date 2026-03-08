import * as React from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import {
  Table,
  TableHeader,
  TableBody,
  TableHead,
  TableRow,
  TableCell,
} from "@/components/ui/table";
import type { ModelArchitectureResponse, LayerNode } from "@/types/model";

interface LayerSummaryTableProps {
  readonly architecture: ModelArchitectureResponse;
}

function formatParamCount(count: number | null): string {
  if (count === null) return "—";
  if (count >= 1_000_000_000) return `${(count / 1_000_000_000).toFixed(2)}B`;
  if (count >= 1_000_000) return `${(count / 1_000_000).toFixed(2)}M`;
  if (count >= 1_000) return `${(count / 1_000).toFixed(1)}K`;
  return String(count);
}

function getTopLevelLayers(tree: LayerNode): ReadonlyArray<LayerNode> {
  const directChildren = tree.children;
  if (!directChildren || directChildren.length === 0) return [tree];
  // If the root has a single wrapper child (e.g. "model"), descend one level
  if (
    directChildren.length === 1 &&
    directChildren[0].children &&
    directChildren[0].children.length > 0
  ) {
    return directChildren[0].children;
  }
  return directChildren;
}

export function LayerSummaryTable({ architecture }: LayerSummaryTableProps): React.JSX.Element {
  const layers = getTopLevelLayers(architecture.tree);

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium">Layer Summary</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Type</TableHead>
              <TableHead className="text-right">Parameters</TableHead>
              <TableHead className="text-center">Trainable</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {layers.map((layer) => (
              <TableRow key={layer.name}>
                <TableCell className="font-mono text-xs">{layer.name}</TableCell>
                <TableCell className="text-xs text-muted-foreground">{layer.type}</TableCell>
                <TableCell className="text-right font-mono text-xs">
                  {formatParamCount(layer.params)}
                </TableCell>
                <TableCell className="text-center text-xs">
                  {layer.trainable === null ? "—" : layer.trainable ? "Yes" : "No"}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
