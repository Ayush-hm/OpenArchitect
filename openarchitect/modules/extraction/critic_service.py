import json
import re

from pydantic import BaseModel, Field, field_validator

from openarchitect.core.contracts.model_provider import ModelProvider
from openarchitect.core.schemas.architecture import AttributeValue
from openarchitect.core.schemas import ArchitectureEdge, ArchitectureGraph, ArchitectureNode, NodeType, RelationshipType
from openarchitect.observability import traceable_step


class NodeRemovalPatch(BaseModel):
    id: str
    reason: str


class NodeUpdatePatch(BaseModel):
    id: str
    name: str | None = None
    type: NodeType | None = None
    attributes: dict[str, AttributeValue] = Field(default_factory=dict)
    evidence: list[str] = Field(default_factory=list)
    reason: str | None = None

    @field_validator("type", mode="before")
    @classmethod
    def empty_type_when_invalid(cls, value):
        if value is None or value in {item.value for item in NodeType}:
            return value
        return NodeType.UNKNOWN


class EdgeRemovalPatch(BaseModel):
    from_node: str = Field(alias="from")
    to_node: str = Field(alias="to")
    relationship: RelationshipType
    reason: str


class GraphCriticPatchOutput(BaseModel):
    remove_nodes: list[NodeRemovalPatch] = Field(default_factory=list)
    add_nodes: list[ArchitectureNode] = Field(default_factory=list)
    update_nodes: list[NodeUpdatePatch] = Field(default_factory=list)
    remove_edges: list[EdgeRemovalPatch] = Field(default_factory=list)
    add_edges: list[ArchitectureEdge] = Field(default_factory=list)
    add_constraints: list[str] = Field(default_factory=list)
    add_unknowns: list[str] = Field(default_factory=list)


@traceable_step(name="Graph Critic", run_type="chain")
async def critique_architecture_graph(
    graph: ArchitectureGraph,
    document_text: str,
    model_provider: ModelProvider,
) -> ArchitectureGraph:
    prompt = f"""
You are the OpenArchitect Graph Critic.

Review the extracted architecture graph against the original SAD and return a
minimal patch. This is a soft semantic validation pass, not a closed set of
architecture rules.

Guidelines:
- Do not create architecture improvements here. This is architecture_v1 cleanup only.
- Add only components, edges, constraints, or unknowns explicitly supported by the SAD.
- Remove edges only when their cited evidence does not actually support that relationship.
- Fix missing explicitly mentioned infrastructure components, such as EKS, Kubernetes,
  worker nodes, databases, buckets, queues, caches, subnets, gateways, or external APIs.
- Do not remove a relationship just because it is uncommon. Remove it only when the SAD
  evidence is unsupported or a better explicitly supported relationship exists.
- Keep the patch minimal. If the graph is acceptable, return empty lists.

Original SAD full text:
{document_text}

Current graph JSON:
{json.dumps(graph.model_dump(by_alias=True), separators=(",", ":"))}
"""
    try:
        patch = await model_provider.generate_structured(prompt, GraphCriticPatchOutput)
    except Exception:
        return graph
    return apply_graph_critic_patch(graph, patch, document_text)


def apply_graph_critic_patch(
    graph: ArchitectureGraph,
    patch: GraphCriticPatchOutput,
    document_text: str,
) -> ArchitectureGraph:
    source = _normalize_for_evidence(document_text)
    updated = graph.model_copy(deep=True)

    _remove_nodes(updated, patch.remove_nodes)
    _remove_edges(updated, patch.remove_edges)
    _add_nodes(updated, patch.add_nodes, source)
    _update_nodes(updated, patch.update_nodes, source)
    _add_edges(updated, patch.add_edges, source)
    _add_text_items(updated.constraints, patch.add_constraints, source)
    _add_text_items(updated.unknowns, patch.add_unknowns, source)

    return updated


def _remove_nodes(graph: ArchitectureGraph, removals: list[NodeRemovalPatch]) -> None:
    remove_ids = {_slug(item.id) for item in removals if item.reason.strip()}
    if not remove_ids:
        return

    graph.nodes = [node for node in graph.nodes if _slug(node.id) not in remove_ids]
    graph.edges = [
        edge
        for edge in graph.edges
        if _slug(edge.from_node) not in remove_ids and _slug(edge.to_node) not in remove_ids
    ]


def _remove_edges(graph: ArchitectureGraph, removals: list[EdgeRemovalPatch]) -> None:
    remove_keys = {
        (_slug(item.from_node), _slug(item.to_node), str(item.relationship))
        for item in removals
        if item.reason.strip()
    }
    if not remove_keys:
        return

    graph.edges = [
        edge
        for edge in graph.edges
        if (_slug(edge.from_node), _slug(edge.to_node), str(edge.relationship)) not in remove_keys
    ]


def _add_nodes(
    graph: ArchitectureGraph,
    nodes: list[ArchitectureNode],
    normalized_source: str,
) -> None:
    existing = {_slug(node.id) for node in graph.nodes}
    for node in nodes:
        node.id = _slug(node.id or node.name)
        if node.id in existing or not _has_patch_evidence(node.evidence, normalized_source):
            continue
        graph.nodes.append(node)
        existing.add(node.id)


def _update_nodes(
    graph: ArchitectureGraph,
    updates: list[NodeUpdatePatch],
    normalized_source: str,
) -> None:
    nodes_by_id = {_slug(node.id): node for node in graph.nodes}
    for update in updates:
        node = nodes_by_id.get(_slug(update.id))
        if node is None or not _has_patch_evidence(update.evidence, normalized_source):
            continue

        if update.name:
            node.name = update.name
        if update.type is not None:
            node.type = update.type
        if update.evidence:
            node.evidence = _dedupe_text([*node.evidence, *update.evidence])
        node.attributes = {**node.attributes, **update.attributes}


def _add_edges(
    graph: ArchitectureGraph,
    edges: list[ArchitectureEdge],
    normalized_source: str,
) -> None:
    node_ids = {_slug(node.id) for node in graph.nodes}
    existing = {
        (_slug(edge.from_node), _slug(edge.to_node), str(edge.relationship))
        for edge in graph.edges
    }
    for edge in edges:
        edge.from_node = _slug(edge.from_node)
        edge.to_node = _slug(edge.to_node)
        key = (edge.from_node, edge.to_node, str(edge.relationship))
        if key in existing:
            continue
        if edge.from_node not in node_ids or edge.to_node not in node_ids:
            continue
        if not _has_patch_evidence(edge.evidence, normalized_source):
            continue
        graph.edges.append(edge)
        existing.add(key)


def _add_text_items(
    existing: list[str],
    additions: list[str],
    normalized_source: str,
) -> None:
    seen = {_normalize_text(item) for item in existing}
    for item in additions:
        normalized_item = _normalize_text(item)
        if not normalized_item or normalized_item in seen:
            continue
        if normalized_item not in normalized_source:
            continue
        existing.append(item)
        seen.add(normalized_item)


def _has_patch_evidence(evidence: list[str], normalized_source: str) -> bool:
    return any(_normalize_text(item) in normalized_source for item in evidence if item.strip())


def _dedupe_text(items: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for item in items:
        key = _normalize_text(item)
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _normalize_for_evidence(value: str) -> str:
    return _normalize_text(value)


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value.lower())).strip()
