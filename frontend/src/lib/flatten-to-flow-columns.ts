import type { LayerNode } from "@/types/model";
import type { FlowColumn, FlowNode } from "@/types/flow";

function computeStructuralFingerprint(node: LayerNode): string {
  const childNames = (node.children ?? []).map((c) => c.name).join(",");
  return `${node.type}:[${childNames}]`;
}

function buildFlowNode({
  node,
  parentPath,
  depth,
  isGroupHeader,
}: {
  node: LayerNode;
  parentPath: string;
  depth: number;
  isGroupHeader: boolean;
}): FlowNode {
  const fullPath = parentPath ? `${parentPath}.${node.name}` : node.name;
  return {
    fullPath,
    name: node.name,
    depth,
    isGroupHeader,
    type: node.type,
    params: node.params,
    shape: node.shape,
    trainable: node.trainable,
  };
}

function sumLeafParams(nodes: ReadonlyArray<FlowNode>): number {
  return nodes.reduce((acc, n) => acc + (n.isGroupHeader ? 0 : (n.params ?? 0)), 0);
}

// Recursively collect all nodes under a given node, including intermediate group headers.
// The given node itself is included (at the given depth), then children are recursed.
// For repeated sibling groups among children, only the first representative is included.
function collectColumnNodes({
  node,
  parentPath,
  depth,
}: {
  node: LayerNode;
  parentPath: string;
  depth: number;
}): ReadonlyArray<FlowNode> {
  const children = node.children ?? [];
  const hasChildren = children.length > 0;
  const selfEntry = buildFlowNode({ node, parentPath, depth, isGroupHeader: hasChildren });

  if (!hasChildren) {
    return [selfEntry];
  }

  const nodePath = parentPath ? `${parentPath}.${node.name}` : node.name;

  // Group consecutive children by structural fingerprint; only recurse into representative
  type Group = { fingerprint: string; first: LayerNode };
  const groups: Group[] = [];
  for (const child of children) {
    const fingerprint = computeStructuralFingerprint(child);
    const last = groups[groups.length - 1];
    if (!last || last.fingerprint !== fingerprint) {
      groups.push({ fingerprint, first: child });
    }
  }

  const childNodes = groups.flatMap(({ first }) =>
    collectColumnNodes({ node: first, parentPath: nodePath, depth: depth + 1 }),
  );

  return [selfEntry, ...childNodes];
}

type NodeGroup = { fingerprint: string; items: ReadonlyArray<LayerNode> };

function groupByFingerprint(nodes: ReadonlyArray<LayerNode>): ReadonlyArray<NodeGroup> {
  const groups: NodeGroup[] = [];
  for (const node of nodes) {
    const fingerprint = computeStructuralFingerprint(node);
    const last = groups[groups.length - 1];
    if (last && last.fingerprint === fingerprint) {
      groups[groups.length - 1] = { fingerprint, items: [...last.items, node] };
    } else {
      groups.push({ fingerprint, items: [node] });
    }
  }
  return groups;
}

function makeColumnLabel({
  representative,
  parentPath,
}: {
  representative: LayerNode;
  parentPath: string;
}): string {
  // Numeric-named nodes (like PyTorch ModuleList indices) use the parent segment as label
  if (/^\d+$/.test(representative.name)) {
    return parentPath.split(".").pop() ?? representative.name;
  }
  return representative.name;
}

// Expand a list of sibling nodes into flow columns.
// Non-repeated intermediate nodes are expanded into their children's columns.
// Repeated groups become a single representative column.
// Leaf nodes (repeated or not) each become their own column.
function expandNodesToColumns({
  nodes,
  parentPath,
  idxRef,
}: {
  nodes: ReadonlyArray<LayerNode>;
  parentPath: string;
  idxRef: { current: number };
}): ReadonlyArray<FlowColumn> {
  const groups = groupByFingerprint(nodes);
  const columns: FlowColumn[] = [];

  for (const group of groups) {
    const representative = group.items[0]!;
    const isRepeated = group.items.length > 1;
    const hasChildren = (representative.children ?? []).length > 0;

    if (isRepeated && hasChildren) {
      // Repeated container group: one representative column showing internal structure.
      // Collect nodes from the representative's children so depth 0 = first real sub-module.
      const repPath = parentPath ? `${parentPath}.${representative.name}` : representative.name;
      const columnNodes = (representative.children ?? []).flatMap((child) =>
        collectColumnNodes({ node: child, parentPath: repPath, depth: 0 }),
      );
      const label = makeColumnLabel({ representative, parentPath });
      columns.push({
        key: `col-${idxRef.current++}-${representative.name}`,
        label,
        totalParams: sumLeafParams(columnNodes) * group.items.length,
        nodes: columnNodes,
        isRepeated: true,
        repeatCount: group.items.length,
      });
    } else if (!isRepeated && hasChildren) {
      // Single intermediate node: expand transparently into its children's columns.
      const childPath = parentPath ? `${parentPath}.${representative.name}` : representative.name;
      const childColumns = expandNodesToColumns({
        nodes: representative.children ?? [],
        parentPath: childPath,
        idxRef,
      });
      columns.push(...childColumns);
    } else {
      // Leaf nodes (repeated or not): each gets its own column.
      for (const item of group.items) {
        const columnNodes = [
          buildFlowNode({ node: item, parentPath, depth: 0, isGroupHeader: false }),
        ];
        columns.push({
          key: `col-${idxRef.current++}-${item.name}`,
          label: item.name,
          totalParams: sumLeafParams(columnNodes),
          nodes: columnNodes,
          isRepeated: false,
          repeatCount: 1,
        });
      }
    }
  }

  return columns;
}

export function flattenToFlowColumns({ tree }: { tree: LayerNode }): ReadonlyArray<FlowColumn> {
  const topLevelChildren = tree.children ?? [];
  if (topLevelChildren.length === 0) return [];

  const idxRef = { current: 0 };
  return expandNodesToColumns({
    nodes: topLevelChildren,
    parentPath: tree.name,
    idxRef,
  });
}
