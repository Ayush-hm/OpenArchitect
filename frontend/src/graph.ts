import type { ArchitectureGraph, ArchitectureNode } from "./types";

export type GraphDiff = {
  addedNodes: string[];
  removedNodes: string[];
  changedAttributes: Array<{
    nodeId: string;
    nodeName: string;
    key: string;
    before: string;
    after: string;
  }>;
  addedConstraints: string[];
  removedConstraints: string[];
  addedEdges: string[];
  removedEdges: string[];
};

export function graphToMermaid(graph: ArchitectureGraph): string {
  const lines = ["flowchart LR"];
  for (const node of graph.nodes) {
    lines.push(`  ${toMermaidId(node.id)}[${sanitizeLabel(nodeLabel(node))}]`);
  }
  for (const edge of graph.edges) {
    lines.push(
      `  ${toMermaidId(edge.from)} -->|${edge.relationship}| ${toMermaidId(edge.to)}`,
    );
  }
  if (graph.edges.length === 0 && graph.nodes.length > 1) {
    for (let index = 0; index < graph.nodes.length - 1; index += 1) {
      lines.push(
        `  ${toMermaidId(graph.nodes[index].id)} --> ${toMermaidId(graph.nodes[index + 1].id)}`,
      );
    }
  }
  return lines.join("\n");
}

export function buildGraphDiff(v1: ArchitectureGraph, v2: ArchitectureGraph): GraphDiff {
  const v1Nodes = new Map(v1.nodes.map((node) => [node.id, node]));
  const v2Nodes = new Map(v2.nodes.map((node) => [node.id, node]));
  const v1NodeIds = new Set(v1Nodes.keys());
  const v2NodeIds = new Set(v2Nodes.keys());
  const v1Edges = new Set(v1.edges.map(edgeKey));
  const v2Edges = new Set(v2.edges.map(edgeKey));
  const v1Constraints = new Set(v1.constraints);
  const v2Constraints = new Set(v2.constraints);

  const changedAttributes: GraphDiff["changedAttributes"] = [];
  for (const [nodeId, beforeNode] of v1Nodes.entries()) {
    const afterNode = v2Nodes.get(nodeId);
    if (!afterNode) {
      continue;
    }
    const keys = new Set([
      ...Object.keys(beforeNode.attributes),
      ...Object.keys(afterNode.attributes),
    ]);
    for (const key of keys) {
      const before = stringifyValue(beforeNode.attributes[key]);
      const after = stringifyValue(afterNode.attributes[key]);
      if (before !== after) {
        changedAttributes.push({
          nodeId,
          nodeName: afterNode.name,
          key,
          before,
          after,
        });
      }
    }
    if (beforeNode.name !== afterNode.name) {
      changedAttributes.push({
        nodeId,
        nodeName: afterNode.name,
        key: "name",
        before: beforeNode.name,
        after: afterNode.name,
      });
    }
  }

  return {
    addedNodes: [...v2NodeIds].filter((id) => !v1NodeIds.has(id)),
    removedNodes: [...v1NodeIds].filter((id) => !v2NodeIds.has(id)),
    changedAttributes,
    addedConstraints: [...v2Constraints].filter((item) => !v1Constraints.has(item)),
    removedConstraints: [...v1Constraints].filter((item) => !v2Constraints.has(item)),
    addedEdges: [...v2Edges].filter((item) => !v1Edges.has(item)),
    removedEdges: [...v1Edges].filter((item) => !v2Edges.has(item)),
  };
}

function nodeLabel(node: ArchitectureNode): string {
  const details = Object.entries(node.attributes)
    .filter(([key, value]) => key !== "target_decision_ids" && value !== null && value !== "")
    .slice(0, 2)
    .map(([key, value]) => `${titleCase(key)}: ${titleCase(String(value))}`);
  return details.length > 0 ? `${node.name} / ${details.join(" / ")}` : node.name;
}

function edgeKey(edge: { from: string; to: string; relationship: string }): string {
  return `${edge.from} -> ${edge.to} (${edge.relationship})`;
}

function toMermaidId(id: string): string {
  return id.replaceAll("-", "_");
}

function sanitizeLabel(value: string): string {
  return value.replaceAll("[", "(").replaceAll("]", ")").replaceAll('"', "'");
}

function stringifyValue(value: unknown): string {
  if (value === undefined || value === null || value === "") {
    return "not set";
  }
  return String(value);
}

function titleCase(value: string): string {
  return value
    .replaceAll("_", " ")
    .replaceAll("-", " ")
    .split(" ")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
