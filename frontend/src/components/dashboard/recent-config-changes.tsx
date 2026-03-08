import * as React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { ConfigSourceTag } from "@/types/config";

export interface RawConfigVersionItem {
  readonly id: string;
  readonly version_number: number;
  readonly created_at: string;
  readonly source_tag: ConfigSourceTag;
  readonly source_detail: string | null;
  readonly diff_from_prev: Record<string, unknown> | null;
}

interface RecentConfigChangesProps {
  readonly items: ReadonlyArray<RawConfigVersionItem>;
  readonly isLoading: boolean;
}

type BadgeVariant = "default" | "secondary" | "destructive" | "outline";

function sourceTagVariant(tag: ConfigSourceTag): BadgeVariant {
  switch (tag) {
    case "user":
      return "secondary";
    case "ai_suggestion":
      return "default";
    case "system":
      return "outline";
    default: {
      const _exhaustive: never = tag;
      return _exhaustive;
    }
  }
}

function countDiffChanges(diff: Record<string, unknown> | null): number {
  if (!diff) return 0;
  const { added, removed, changed } = diff as {
    added?: Record<string, unknown>;
    removed?: Record<string, unknown>;
    changed?: Record<string, unknown>;
  };
  return (
    Object.keys(added ?? {}).length +
    Object.keys(removed ?? {}).length +
    Object.keys(changed ?? {}).length
  );
}

function formatTimestamp(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function RecentConfigChanges({
  items,
  isLoading,
}: RecentConfigChangesProps): React.JSX.Element {
  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Recent Config Changes</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">Loading...</CardContent>
      </Card>
    );
  }

  if (items.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Recent Config Changes</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">No config versions yet.</CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Recent Config Changes</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <ul className="divide-y">
          {items.map((item) => {
            const changeCount = countDiffChanges(item.diff_from_prev);
            return (
              <li key={item.id} className="flex items-start justify-between px-4 py-3 gap-2">
                <div className="min-w-0">
                  <div className="text-xs font-medium">v{item.version_number}</div>
                  <div className="text-xs text-muted-foreground">
                    {formatTimestamp(item.created_at)}
                  </div>
                  {changeCount > 0 && (
                    <div className="text-xs text-muted-foreground">
                      {changeCount} field{changeCount !== 1 ? "s" : ""} changed
                    </div>
                  )}
                </div>
                <Badge variant={sourceTagVariant(item.source_tag)} className="text-xs shrink-0">
                  {item.source_tag.replace(/_/g, " ")}
                </Badge>
              </li>
            );
          })}
        </ul>
      </CardContent>
    </Card>
  );
}
