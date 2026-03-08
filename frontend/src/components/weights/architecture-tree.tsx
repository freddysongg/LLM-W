import * as React from "react";
import type { LayerNode } from "@/types/model";

interface ArchitectureTreeProps {
  readonly tree: LayerNode;
  readonly onSelectLayer: (name: string) => void;
  readonly searchQuery: string;
}

function formatParamCount(params: number): string {
  if (params >= 1e9) return `${(params / 1e9).toFixed(2)}B`;
  if (params >= 1e6) return `${(params / 1e6).toFixed(2)}M`;
  if (params >= 1e3) return `${(params / 1e3).toFixed(1)}K`;
  return String(params);
}

function nodeMatchesSearch({ node, query }: { node: LayerNode; query: string }): boolean {
  if (!query) return true;
  const lower = query.toLowerCase();
  return node.name.toLowerCase().includes(lower) || node.type.toLowerCase().includes(lower);
}

function subtreeHasMatch({ node, query }: { node: LayerNode; query: string }): boolean {
  if (nodeMatchesSearch({ node, query })) return true;
  return (node.children ?? []).some((child) => subtreeHasMatch({ node: child, query }));
}

interface TreeNodeProps {
  readonly node: LayerNode;
  readonly fullPath: string;
  readonly depth: number;
  readonly searchQuery: string;
  readonly expandedPaths: Set<string>;
  readonly onToggleExpand: (path: string) => void;
  readonly onSelectLayer: (name: string) => void;
}

function TreeNode({
  node,
  fullPath,
  depth,
  searchQuery,
  expandedPaths,
  onToggleExpand,
  onSelectLayer,
}: TreeNodeProps): React.JSX.Element | null {
  const hasChildren = (node.children ?? []).length > 0;
  const isExpanded = expandedPaths.has(fullPath);
  const isDirectMatch = nodeMatchesSearch({ node, query: searchQuery });

  if (searchQuery && !subtreeHasMatch({ node, query: searchQuery })) {
    return null;
  }

  return (
    <div>
      <div
        className={`flex items-center gap-1 py-0.5 rounded cursor-pointer text-sm hover:bg-muted/50 ${isDirectMatch && searchQuery ? "bg-yellow-50 dark:bg-yellow-950/20" : ""}`}
        style={{ paddingLeft: `${depth * 16 + 4}px` }}
        onClick={() => {
          if (hasChildren) {
            onToggleExpand(fullPath);
          } else {
            onSelectLayer(fullPath);
          }
        }}
      >
        <span className="w-4 shrink-0 text-center text-muted-foreground text-xs">
          {hasChildren ? (isExpanded ? "▾" : "▸") : ""}
        </span>
        <span className="font-mono text-xs font-medium truncate">{node.name}</span>
        <span className="text-xs text-muted-foreground ml-1 shrink-0">{node.type}</span>
        {node.params !== null && node.params > 0 && (
          <span className="ml-auto text-xs text-muted-foreground shrink-0 pr-2">
            {formatParamCount(node.params)}
          </span>
        )}
        {node.trainable === false && (
          <span className="text-xs text-muted-foreground/50 shrink-0 pr-1">[frozen]</span>
        )}
      </div>
      {hasChildren && isExpanded && (
        <div>
          {(node.children ?? []).map((child) => {
            const childPath = `${fullPath}.${child.name}`;
            return (
              <TreeNode
                key={childPath}
                node={child}
                fullPath={childPath}
                depth={depth + 1}
                searchQuery={searchQuery}
                expandedPaths={expandedPaths}
                onToggleExpand={onToggleExpand}
                onSelectLayer={onSelectLayer}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}

export function ArchitectureTree({
  tree,
  onSelectLayer,
  searchQuery,
}: ArchitectureTreeProps): React.JSX.Element {
  const rootPath = tree.name;
  const [expandedPaths, setExpandedPaths] = React.useState<Set<string>>(() => new Set([rootPath]));

  const handleToggleExpand = (path: string): void => {
    setExpandedPaths((prev) => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  };

  return (
    <div className="overflow-auto border rounded-md bg-background p-1">
      <TreeNode
        node={tree}
        fullPath={rootPath}
        depth={0}
        searchQuery={searchQuery}
        expandedPaths={expandedPaths}
        onToggleExpand={handleToggleExpand}
        onSelectLayer={onSelectLayer}
      />
    </div>
  );
}
