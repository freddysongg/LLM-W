import * as React from "react";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";
import type { ProjectStorageResponse } from "@/types/project";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

const CATEGORY_COLORS: Record<string, string> = {
  checkpoints: "#6366f1",
  logs: "#22c55e",
  activations: "#f59e0b",
  exports: "#3b82f6",
  configs: "#ec4899",
};

interface StorageSummaryProps {
  readonly storage: ProjectStorageResponse;
  readonly isCleaningUp: boolean;
  readonly onCleanup: () => void;
}

export function StorageSummary({
  storage,
  isCleaningUp,
  onCleanup,
}: StorageSummaryProps): React.JSX.Element {
  const { totalBytes, breakdown, retentionPolicy } = storage;

  const chartData = Object.entries(breakdown)
    .filter(([, detail]) => detail.bytes > 0)
    .map(([category, detail]) => ({
      name: category,
      value: detail.bytes,
      label: formatBytes(detail.bytes),
    }));

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">Storage</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="text-2xl font-semibold">{formatBytes(totalBytes)}</div>

        {chartData.length > 0 && (
          <ResponsiveContainer width="100%" height={160}>
            <PieChart>
              <Pie
                data={chartData}
                cx="50%"
                cy="50%"
                innerRadius={40}
                outerRadius={70}
                dataKey="value"
                paddingAngle={2}
              >
                {chartData.map(({ name }) => (
                  <Cell key={name} fill={CATEGORY_COLORS[name] ?? "#94a3b8"} />
                ))}
              </Pie>
              <Tooltip
                formatter={(value: number) => formatBytes(value)}
                labelFormatter={(label: string) => label}
              />
            </PieChart>
          </ResponsiveContainer>
        )}

        <div className="space-y-1">
          {Object.entries(breakdown).map(([category, detail]) => (
            <div key={category} className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-1.5">
                <div
                  className="w-2 h-2 rounded-full"
                  style={{ backgroundColor: CATEGORY_COLORS[category] ?? "#94a3b8" }}
                />
                <span className="capitalize text-muted-foreground">{category}</span>
              </div>
              <span className="font-medium">{formatBytes(detail.bytes)}</span>
            </div>
          ))}
        </div>

        {retentionPolicy.reclaimableBytes > 0 && (
          <div className="rounded-md bg-muted/50 p-3 space-y-2">
            <div className="text-xs text-muted-foreground">
              {formatBytes(retentionPolicy.reclaimableBytes)} reclaimable (
              {retentionPolicy.reclaimableCheckpoints} checkpoints)
            </div>
            <Button
              size="sm"
              variant="outline"
              className="w-full"
              onClick={onCleanup}
              disabled={isCleaningUp}
            >
              {isCleaningUp ? "Cleaning up…" : "Run cleanup"}
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
