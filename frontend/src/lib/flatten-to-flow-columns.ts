import type { LayerNode } from "@/types/model";
import type { FlowColumn, FlowNode } from "@/types/flow";

function computeStructuralFingerprint(node: LayerNode): string {
  const childNames = (node.children ?? []).map((c) => c.name).join(",");
  return `${node.type}:[${childNames}]`;
}

function buildFlowNode({ node, parentPath }: { node: LayerNode; parentPath: string }): FlowNode {
  const fullPath = parentPath ? `${parentPath}.${node.name}` : node.name;
  return {
    fullPath,
    name: node.name,
    type: node.type,
    params: node.params,
    shape: node.shape,
    trainable: node.trainable,
  };
}

function sumParams(nodes: ReadonlyArray<FlowNode>): number {
  return nodes.reduce((acc, n) => acc + (n.params ?? 0), 0);
}

function buildColumnNodes({
  node,
  parentPath,
}: {
  node: LayerNode;
  parentPath: string;
}): ReadonlyArray<FlowNode> {
  const children = node.children ?? [];
  if (children.length === 0) {
    return [buildFlowNode({ node, parentPath })];
  }
  const nodePath = parentPath ? `${parentPath}.${node.name}` : node.name;
  return children.map((child) => buildFlowNode({ node: child, parentPath: nodePath }));
}

export function flattenToFlowColumns({ tree }: { tree: LayerNode }): ReadonlyArray<FlowColumn> {
  const topLevelChildren = tree.children ?? [];
  if (topLevelChildren.length === 0) {
    return [];
  }

  const rootPath = tree.name;

  // Group consecutive children by structural fingerprint
  type Group = { fingerprint: string; items: ReadonlyArray<LayerNode> };
  const groups: Group[] = [];

  for (const child of topLevelChildren) {
    const fingerprint = computeStructuralFingerprint(child);
    const last = groups[groups.length - 1];
    if (last && last.fingerprint === fingerprint) {
      groups[groups.length - 1] = {
        fingerprint,
        items: [...last.items, child],
      };
    } else {
      groups.push({ fingerprint, items: [child] });
    }
  }

  return groups.map((group, idx): FlowColumn => {
    const isRepeated = group.items.length > 1;
    // Use the first item as the representative for node structure
    const representative = group.items[0]!;
    const nodes = buildColumnNodes({ node: representative, parentPath: rootPath });
    const totalParams = sumParams(nodes) * group.items.length;

    return {
      key: `col-${idx}-${representative.name}`,
      label: representative.name,
      totalParams,
      nodes,
      isRepeated,
      repeatCount: group.items.length,
    };
  });
}
