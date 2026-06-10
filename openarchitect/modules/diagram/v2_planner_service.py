import re
from copy import deepcopy
from typing import Any

from pydantic import BaseModel, Field, field_validator

from openarchitect.core.contracts.model_provider import ModelProvider
from openarchitect.core.schemas import (
    ADR,
    ArchitectureDecision,
    ArchitectureEdge,
    ArchitectureGraph,
    ArchitectureNode,
    NodeType,
    RelationshipType,
)
from openarchitect.core.schemas.architecture import AttributeValue
from openarchitect.modules.diagram.service import build_architecture_v2


class V2NodeAddPatch(BaseModel):
    id: str
    name: str
    type: NodeType = NodeType.UNKNOWN
    attributes: dict[str, AttributeValue] = Field(default_factory=dict)
    decision_ids: list[str] = Field(default_factory=list)
    reason: str

    @field_validator("type", mode="before")
    @classmethod
    def unknown_type_when_invalid(cls, value):
        if value in {item.value for item in NodeType}:
            return value
        return NodeType.UNKNOWN


class V2NodeUpdatePatch(BaseModel):
    id: str
    name: str | None = None
    type: NodeType | None = None
    attributes: dict[str, AttributeValue] = Field(default_factory=dict)
    remove_attributes: list[str] = Field(default_factory=list)
    decision_ids: list[str] = Field(default_factory=list)
    reason: str

    @field_validator("type", mode="before")
    @classmethod
    def empty_type_when_invalid(cls, value):
        if value is None or value in {item.value for item in NodeType}:
            return value
        return NodeType.UNKNOWN


class V2EdgeAddPatch(BaseModel):
    from_node: str = Field(alias="from")
    to_node: str = Field(alias="to")
    relationship: RelationshipType
    description: str | None = None
    decision_ids: list[str] = Field(default_factory=list)
    reason: str


class V2EdgeRemovalPatch(BaseModel):
    from_node: str = Field(alias="from")
    to_node: str = Field(alias="to")
    relationship: RelationshipType
    decision_ids: list[str] = Field(default_factory=list)
    reason: str


class V2ConstraintPatch(BaseModel):
    text: str
    decision_ids: list[str] = Field(default_factory=list)
    reason: str


class ArchitectureV2PatchOutput(BaseModel):
    add_nodes: list[V2NodeAddPatch] = Field(default_factory=list)
    update_nodes: list[V2NodeUpdatePatch] = Field(default_factory=list)
    remove_edges: list[V2EdgeRemovalPatch] = Field(default_factory=list)
    add_edges: list[V2EdgeAddPatch] = Field(default_factory=list)
    remove_constraints: list[V2ConstraintPatch] = Field(default_factory=list)
    add_constraints: list[V2ConstraintPatch] = Field(default_factory=list)


async def plan_architecture_v2_with_llm(
    graph: ArchitectureGraph,
    decisions: list[ArchitectureDecision],
    adrs: list[ADR],
    model_provider: ModelProvider,
) -> ArchitectureGraph:
    if not decisions:
        return graph.model_copy(deep=True)

    prompt = f"""
You are the OpenArchitect Architecture v2 Planner.

Apply the validated architecture decisions to create a target-state graph patch.
Return only patch operations. Do not restate the whole graph.

Rules:
- Every patch operation must reference one or more decision_ids.
- Update existing nodes when a decision changes their target state.
- Add new nodes only when a decision explicitly introduces a new target component.
- Remove source constraints that are contradicted by target decisions.
- Add target constraints only when they summarize a decision-backed target state.
- Do not invent unrelated architecture improvements.
- Prefer graph attributes and node names that make the target diagram understandable.

Architecture v1 JSON:
{graph.model_dump_json(by_alias=True)}

Validated decisions JSON:
{[decision.model_dump() for decision in decisions]}

ADRs JSON:
{[adr.model_dump() for adr in adrs]}
"""
    try:
        patch = await model_provider.generate_structured(prompt, ArchitectureV2PatchOutput)
    except Exception:
        return build_architecture_v2(graph, decisions)
    return apply_architecture_v2_patch(graph, patch, decisions, adrs)


def apply_architecture_v2_patch(
    graph: ArchitectureGraph,
    patch: ArchitectureV2PatchOutput,
    decisions: list[ArchitectureDecision],
    adrs: list[ADR],
) -> ArchitectureGraph:
    updated = deepcopy(graph)
    decision_ids = {decision.id for decision in decisions} | {adr.id for adr in adrs}
    if not decision_ids:
        return updated

    _remove_edges(updated, patch.remove_edges, decision_ids)
    _add_nodes(updated, patch.add_nodes, decision_ids)
    _update_nodes(updated, patch.update_nodes, decision_ids)
    _add_edges(updated, patch.add_edges, decision_ids)
    _remove_constraints(updated, patch.remove_constraints, decision_ids)
    _add_constraints(updated, patch.add_constraints, decision_ids)
    _cleanup_stale_constraints(updated, patch, decisions, decision_ids)
    return updated


def _remove_edges(
    graph: ArchitectureGraph,
    removals: list[V2EdgeRemovalPatch],
    decision_ids: set[str],
) -> None:
    remove_keys = {
        (_slug(item.from_node), _slug(item.to_node), str(item.relationship))
        for item in removals
        if _decision_backed(item.decision_ids, decision_ids) and item.reason.strip()
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
    nodes: list[V2NodeAddPatch],
    decision_ids: set[str],
) -> None:
    existing = {_slug(node.id) for node in graph.nodes}
    for item in nodes:
        node_id = _slug(item.id)
        if node_id in existing:
            continue
        if not _decision_backed(item.decision_ids, decision_ids) or not item.reason.strip():
            continue
        graph.nodes.append(
            ArchitectureNode(
                id=node_id,
                name=item.name,
                type=item.type,
                attributes={
                    **item.attributes,
                    "target_decision_ids": ",".join(item.decision_ids),
                },
            )
        )
        existing.add(node_id)


def _update_nodes(
    graph: ArchitectureGraph,
    updates: list[V2NodeUpdatePatch],
    decision_ids: set[str],
) -> None:
    nodes_by_id = {_slug(node.id): node for node in graph.nodes}
    for item in updates:
        if not _decision_backed(item.decision_ids, decision_ids) or not item.reason.strip():
            continue
        node = nodes_by_id.get(_slug(item.id))
        if node is None:
            continue
        if item.name:
            node.name = item.name
        if item.type is not None:
            node.type = item.type
        for key in item.remove_attributes:
            node.attributes.pop(key, None)
        if item.attributes:
            node.attributes = {
                **node.attributes,
                **item.attributes,
                "target_decision_ids": ",".join(item.decision_ids),
            }


def _add_edges(
    graph: ArchitectureGraph,
    edges: list[V2EdgeAddPatch],
    decision_ids: set[str],
) -> None:
    node_ids = {_slug(node.id) for node in graph.nodes}
    existing = {
        (_slug(edge.from_node), _slug(edge.to_node), str(edge.relationship))
        for edge in graph.edges
    }
    for item in edges:
        if not _decision_backed(item.decision_ids, decision_ids) or not item.reason.strip():
            continue
        from_node = _slug(item.from_node)
        to_node = _slug(item.to_node)
        key = (from_node, to_node, str(item.relationship))
        if from_node not in node_ids or to_node not in node_ids or key in existing:
            continue
        graph.edges.append(
            ArchitectureEdge(
                **{
                    "from": from_node,
                    "to": to_node,
                    "relationship": item.relationship,
                    "description": item.description,
                }
            )
        )
        existing.add(key)


def _remove_constraints(
    graph: ArchitectureGraph,
    removals: list[V2ConstraintPatch],
    decision_ids: set[str],
) -> None:
    targets = {
        _normalize_text(item.text)
        for item in removals
        if _decision_backed(item.decision_ids, decision_ids) and item.reason.strip()
    }
    if not targets:
        return
    graph.constraints = [
        item for item in graph.constraints if _normalize_text(item) not in targets
    ]


def _add_constraints(
    graph: ArchitectureGraph,
    additions: list[V2ConstraintPatch],
    decision_ids: set[str],
) -> None:
    seen = {_normalize_text(item) for item in graph.constraints}
    for item in additions:
        normalized = _normalize_text(item.text)
        if not normalized or normalized in seen:
            continue
        if not _decision_backed(item.decision_ids, decision_ids) or not item.reason.strip():
            continue
        graph.constraints.append(item.text)
        seen.add(normalized)


def _cleanup_stale_constraints(
    graph: ArchitectureGraph,
    patch: ArchitectureV2PatchOutput,
    decisions: list[ArchitectureDecision],
    decision_ids: set[str],
) -> None:
    target_text = _target_state_text(patch, decisions, decision_ids)
    if not target_text:
        return

    graph.constraints = [
        constraint
        for constraint in graph.constraints
        if not _is_contradicted_source_constraint(constraint, target_text)
    ]


def _target_state_text(
    patch: ArchitectureV2PatchOutput,
    decisions: list[ArchitectureDecision],
    decision_ids: set[str],
) -> str:
    parts: list[str] = []
    for decision in decisions:
        parts.extend(
            [
                decision.title,
                decision.context,
                decision.decision,
                *decision.diagram_changes,
            ]
        )
    for item in patch.update_nodes:
        if not _decision_backed(item.decision_ids, decision_ids):
            continue
        parts.extend([item.id, item.name or "", item.reason, *_attribute_parts(item.attributes)])
    for item in patch.add_nodes:
        if not _decision_backed(item.decision_ids, decision_ids):
            continue
        parts.extend([item.id, item.name, item.reason, *_attribute_parts(item.attributes)])
    for item in patch.add_constraints:
        if not _decision_backed(item.decision_ids, decision_ids):
            continue
        parts.extend([item.text, item.reason])
    return _normalize_text(" ".join(parts))


def _attribute_parts(attributes: dict[str, Any]) -> list[str]:
    return [f"{key} {value}" for key, value in attributes.items()]


def _is_contradicted_source_constraint(constraint: str, target_text: str) -> bool:
    normalized = _normalize_text(constraint)
    if not normalized:
        return False

    constraint_terms = _significant_terms(normalized)
    shared_subject_terms = [
        term
        for term in constraint_terms
        if term not in _SOURCE_STATE_TERMS and term in target_text
    ]
    if not shared_subject_terms:
        return False

    return any(
        source_term in normalized and any(target_term in target_text for target_term in target_terms)
        for source_term, target_terms in _CONTRADICTION_TERMS.items()
    )


def _decision_backed(ids: list[str], valid_ids: set[str]) -> bool:
    return bool(ids) and all(item in valid_ids for item in ids)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value.lower())).strip()


def _significant_terms(value: str) -> list[str]:
    generic = {
        "architecture",
        "constraint",
        "deployment",
        "service",
        "services",
        "state",
        "target",
    }
    return [
        term
        for term in re.findall(r"[a-z0-9]+", value)
        if len(term) > 2 and term not in generic
    ]


_CONTRADICTION_TERMS: dict[str, tuple[str, ...]] = {
    "disabled": ("enabled", "enforced", "implemented"),
    "single": ("multi", "cluster", "clustered", "redundant", "replicated", "failover"),
    "public": ("private", "isolated"),
    "missing": ("defined", "implemented", "enabled"),
    "undefined": ("defined", "implemented"),
    "unavailable": ("available", "enabled"),
    "unencrypted": ("encrypted", "encryption enabled"),
    "not": ("defined", "implemented", "enabled", "enforced"),
    "no": ("defined", "implemented", "enabled", "enforced"),
}

_SOURCE_STATE_TERMS = set(_CONTRADICTION_TERMS)
