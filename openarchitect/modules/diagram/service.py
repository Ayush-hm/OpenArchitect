from copy import deepcopy

from openarchitect.core.schemas import (
    ArchitectureDecision,
    ArchitectureEdge,
    ArchitectureGraph,
    ArchitectureNode,
    DiagramSpec,
    NodeType,
    RelationshipType,
)


def build_architecture_v2(
    graph: ArchitectureGraph,
    decisions: list[ArchitectureDecision],
) -> ArchitectureGraph:
    updated = deepcopy(graph)
    node_ids = {node.id for node in updated.nodes}

    for decision in decisions:
        title = decision.title.lower()
        if "multi-az" in title:
            _mark_primary_database_ha(updated)
        if "cache" in title and "redis" not in node_ids:
            updated.nodes.append(ArchitectureNode(id="redis", name="Redis", type=NodeType.CACHE))
            node_ids.add("redis")
            _add_edge(updated, _main_service_id(updated), "redis", RelationshipType.READS_FROM)
            _add_edge(updated, "redis", _primary_data_store_id(updated), RelationshipType.DEPENDS_ON)
        if "queue" in title and "queue" not in node_ids:
            updated.nodes.append(ArchitectureNode(id="queue", name="Queue", type=NodeType.QUEUE))
            updated.nodes.append(ArchitectureNode(id="worker", name="Worker", type=NodeType.WORKER))
            node_ids.update({"queue", "worker"})
            _add_edge(updated, _main_service_id(updated), "queue", RelationshipType.PUBLISHES)
            _add_edge(updated, "queue", "worker", RelationshipType.SUBSCRIBES_TO)
            _add_edge(updated, "worker", _email_service_id(updated), RelationshipType.CALLS)
        if "authentication" in title and "api-gateway" not in node_ids:
            updated.nodes.append(
                ArchitectureNode(id="api-gateway", name="API Gateway", type=NodeType.SERVICE)
            )
            node_ids.add("api-gateway")
            _add_edge(updated, "frontend", "api-gateway", RelationshipType.ROUTES_TO)
            _add_edge(updated, "api-gateway", _main_service_id(updated), RelationshipType.AUTHENTICATES)
        if "fraud inference" in title and "fraud-inference-boundary" not in node_ids:
            updated.nodes.append(
                ArchitectureNode(
                    id="fraud-inference-boundary",
                    name="Fraud Inference Boundary",
                    type=NodeType.SERVICE,
                )
            )
            node_ids.add("fraud-inference-boundary")
            _add_edge(updated, "fraud-detection-service", "fraud-inference-boundary", RelationshipType.CALLS)
            _add_edge(updated, "fraud-inference-boundary", "gpu-nodes", RelationshipType.USES)

    return updated


def generate_mermaid(graph: ArchitectureGraph) -> DiagramSpec:
    lines = ["flowchart LR"]

    for node in graph.nodes:
        lines.append(f"  {_mermaid_id(node.id)}[{_node_label(node)}]")

    for edge in graph.edges:
        lines.append(
            f"  {_mermaid_id(edge.from_node)} -->|{edge.relationship}| {_mermaid_id(edge.to_node)}"
        )

    if not graph.edges and len(graph.nodes) > 1:
        for left, right in zip(graph.nodes, graph.nodes[1:]):
            lines.append(f"  {_mermaid_id(left.id)} --> {_mermaid_id(right.id)}")

    return DiagramSpec(content="\n".join(lines))


def _mermaid_id(node_id: str) -> str:
    return node_id.replace("-", "_")


def _node_label(node: ArchitectureNode) -> str:
    details = _display_attributes(node.attributes)
    if not details:
        return node.name
    return f"{node.name} / {' / '.join(details)}"


def _display_attributes(attributes: dict) -> list[str]:
    ignored = {"target_decision_ids"}
    details: list[str] = []
    for key, value in attributes.items():
        if key in ignored or value is None or value == "":
            continue
        formatted_key = key.replace("_", " ").title()
        formatted_value = str(value).replace("_", " ").title()
        if formatted_value.lower() in {"true", "false"}:
            formatted_value = formatted_value.lower()
        details.append(f"{formatted_key}: {formatted_value}")
        if len(details) == 2:
            break
    return details


def _add_edge(
    graph: ArchitectureGraph,
    from_node: str,
    to_node: str,
    relationship: RelationshipType,
) -> None:
    if not from_node or not to_node:
        return
    key = (from_node, to_node, relationship)
    existing = {(edge.from_node, edge.to_node, edge.relationship) for edge in graph.edges}
    if key in existing:
        return
    graph.edges.append(
        ArchitectureEdge(
            **{
                "from": from_node,
                "to": to_node,
                "relationship": relationship,
            }
        )
    )


def _main_service_id(graph: ArchitectureGraph) -> str:
    for candidate in ("backend-api", "payments-service", "api"):
        if any(node.id == candidate for node in graph.nodes):
            return candidate
    for node in graph.nodes:
        if node.type == NodeType.SERVICE and node.id not in {"frontend", "api-gateway"}:
            return node.id
    return ""


def _primary_data_store_id(graph: ArchitectureGraph) -> str:
    for preferred in ("postgresql-database", "aurora"):
        if any(node.id == preferred for node in graph.nodes):
            return preferred
    for node in graph.nodes:
        if node.type == NodeType.DATA_STORE:
            return node.id
    return ""


def _email_service_id(graph: ArchitectureGraph) -> str:
    for node in graph.nodes:
        if "email" in node.name.lower():
            return node.id
    return ""


def _mark_primary_database_ha(graph: ArchitectureGraph) -> None:
    primary_id = _primary_data_store_id(graph)
    for node in graph.nodes:
        if node.id == primary_id:
            node.attributes["availability"] = "multi-az"
