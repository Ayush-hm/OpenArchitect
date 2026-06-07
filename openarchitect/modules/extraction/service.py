import re
from dataclasses import dataclass

from openarchitect.core.schemas import (
    ArchitectureEdge,
    ArchitectureGraph,
    ArchitectureNode,
    NodeType,
    RelationshipType,
)


@dataclass(frozen=True)
class ComponentSpec:
    id: str
    name: str
    type: NodeType
    aliases: tuple[str, ...]


COMPONENTS: tuple[ComponentSpec, ...] = (
    ComponentSpec("internet", "Internet", NodeType.USER, ("internet", "user", "users")),
    ComponentSpec("frontend", "Frontend", NodeType.SERVICE, ("frontend", "web app", "ui")),
    ComponentSpec("api-gateway", "API Gateway", NodeType.SERVICE, ("api gateway",)),
    ComponentSpec("backend-api", "Backend API", NodeType.SERVICE, ("backend api",)),
    ComponentSpec("authentication-service", "Authentication Service", NodeType.SERVICE, ("authentication service", "auth service")),
    ComponentSpec("payments-service", "Payments Service", NodeType.SERVICE, ("payments service", "payment service")),
    ComponentSpec("reporting-service", "Reporting Service", NodeType.SERVICE, ("reporting service",)),
    ComponentSpec("fraud-detection-service", "Fraud Detection Service", NodeType.SERVICE, ("fraud detection service", "fraud service")),
    ComponentSpec("postgresql-database", "PostgreSQL Database", NodeType.DATA_STORE, ("postgresql database", "postgres database", "postgresql", "postgres", "database", "db")),
    ComponentSpec("aurora", "Aurora", NodeType.DATA_STORE, ("aurora",)),
    ComponentSpec("redis", "Redis", NodeType.CACHE, ("redis", "cache")),
    ComponentSpec("queue", "Queue", NodeType.QUEUE, ("message queue", "queue")),
    ComponentSpec("worker", "Worker", NodeType.WORKER, ("worker",)),
    ComponentSpec("email-service", "Email Service", NodeType.EXTERNAL_SYSTEM, ("email service",)),
    ComponentSpec("stripe-api", "Stripe API", NodeType.EXTERNAL_SYSTEM, ("stripe api", "stripe")),
    ComponentSpec("payment-provider", "Payment Provider", NodeType.EXTERNAL_SYSTEM, ("payment provider",)),
    ComponentSpec("gpu-nodes", "GPU Nodes", NodeType.EXTERNAL_SYSTEM, ("gpu nodes", "gpu node")),
    ComponentSpec("shared-s3-bucket", "Shared S3 Bucket", NodeType.DATA_STORE, ("shared s3 bucket", "s3 bucket", "s3")),
    ComponentSpec("all-services", "All Services", NodeType.SERVICE, ("all services",)),
)


def extract_architecture(document_text: str) -> ArchitectureGraph:
    """Extract a lightweight architecture graph from text.

    This deterministic extractor is the MVP baseline. A Nemotron-backed extractor
    can later replace this implementation while preserving the same output schema.
    """
    lowered = document_text.lower()
    nodes_by_alias, nodes_by_id = _extract_nodes(lowered)

    edges = _extract_edges(document_text, nodes_by_alias)
    unknowns = _extract_unknowns(lowered)

    if not nodes_by_id:
        unknowns.append("No explicit architecture components were detected.")

    return ArchitectureGraph(
        nodes=list(nodes_by_id.values()),
        edges=edges,
        constraints=_extract_constraints(lowered),
        unknowns=unknowns,
    )


def _extract_nodes(
    lowered: str,
) -> tuple[dict[str, ArchitectureNode], dict[str, ArchitectureNode]]:
    nodes_by_alias: dict[str, ArchitectureNode] = {}
    nodes_by_id: dict[str, ArchitectureNode] = {}

    for spec in COMPONENTS:
        matched_aliases = [alias for alias in spec.aliases if _contains_alias(lowered, alias)]
        if not matched_aliases:
            continue

        node = ArchitectureNode(id=spec.id, name=spec.name, type=spec.type)
        nodes_by_id[spec.id] = node
        for alias in spec.aliases:
            nodes_by_alias[alias] = node

    for name in _extract_named_components(lowered):
        node_id = _slug(name)
        if node_id in nodes_by_id:
            continue
        node_type = _infer_node_type(name)
        node = ArchitectureNode(id=node_id, name=_display_name(name), type=node_type)
        nodes_by_id[node_id] = node
        nodes_by_alias[name] = node

    return nodes_by_alias, nodes_by_id


def _extract_edges(
    document_text: str,
    nodes_by_alias: dict[str, ArchitectureNode],
) -> list[ArchitectureEdge]:
    edges: list[ArchitectureEdge] = []
    sentences = re.split(r"[.;\n]+", document_text)

    for sentence in sentences:
        lowered = sentence.lower()
        mentioned = _mentions_in_order(lowered, nodes_by_alias)
        if len(mentioned) < 2:
            continue

        if "→" in sentence or "->" in sentence or "←" in sentence or "<-" in sentence:
            edges.extend(_extract_flow_edges(sentence, mentioned))
        else:
            relationship = _relationship_from_sentence(lowered)
            edges.append(
                ArchitectureEdge(
                    **{
                        "from": mentioned[0].id,
                        "to": mentioned[1].id,
                        "relationship": relationship,
                        "description": sentence.strip(),
                    }
                )
            )

        edges.extend(_domain_edges_from_sentence(sentence, mentioned))

    return _dedupe_edges(edges)


def _relationship_from_sentence(sentence: str) -> RelationshipType:
    if "backup" in sentence or "stored data" in sentence or "shared s3" in sentence:
        return RelationshipType.STORES_IN
    if "read" in sentence:
        return RelationshipType.READS_FROM
    if "write" in sentence:
        return RelationshipType.WRITES_TO
    if "synchronous" in sentence or "calls" in sentence or "call" in sentence:
        return RelationshipType.CALLS
    return RelationshipType.DEPENDS_ON


def _extract_flow_edges(
    sentence: str,
    mentioned: list[ArchitectureNode],
) -> list[ArchitectureEdge]:
    edges: list[ArchitectureEdge] = []
    description = sentence.strip()
    compacted = _collapse_repeated_nodes(mentioned)
    if "←" in sentence or "<-" in sentence:
        compacted = list(reversed(compacted))

    for source, target in zip(compacted, compacted[1:]):
        if source.id == "postgresql-database" and target.id in {"payments-service", "reporting-service", "fraud-detection-service"}:
            continue
        relationship = _flow_relationship(source, target)
        edges.append(
            ArchitectureEdge(
                **{
                    "from": source.id,
                    "to": target.id,
                    "relationship": relationship,
                    "description": description,
                }
            )
        )
    return edges


def _domain_edges_from_sentence(
    sentence: str,
    mentioned: list[ArchitectureNode],
) -> list[ArchitectureEdge]:
    lowered = sentence.lower()
    ids = {node.id for node in mentioned}
    edges: list[ArchitectureEdge] = []

    def add(source: str, target: str, relationship: RelationshipType) -> None:
        if source in ids and target in ids:
            edges.append(
                ArchitectureEdge(
                    **{
                        "from": source,
                        "to": target,
                        "relationship": relationship,
                        "description": sentence.strip(),
                    }
                )
            )

    if "payments service" in lowered and ("postgres" in lowered or "database" in lowered):
        add("payments-service", "postgresql-database", RelationshipType.WRITES_TO)
    if "reporting service" in lowered and ("postgres" in lowered or "database" in lowered):
        add("reporting-service", "postgresql-database", RelationshipType.READS_FROM)
    if "payments service" in lowered and "stripe" in lowered:
        add("payments-service", "stripe-api", RelationshipType.CALLS)
    if "fraud detection service" in lowered and "gpu" in lowered:
        add("fraud-detection-service", "gpu-nodes", RelationshipType.USES)
    if "shared s3 bucket" in lowered or "s3 bucket" in lowered:
        for node_id in ids:
            if node_id.endswith("-service") or node_id == "all-services":
                add(node_id, "shared-s3-bucket", RelationshipType.STORES_IN)

    return edges


def _flow_relationship(source: ArchitectureNode, target: ArchitectureNode) -> RelationshipType:
    if target.type == NodeType.DATA_STORE:
        if target.id == "shared-s3-bucket":
            return RelationshipType.STORES_IN
        if source.id == "reporting-service":
            return RelationshipType.READS_FROM
        return RelationshipType.WRITES_TO
    if target.id == "gpu-nodes":
        return RelationshipType.USES
    if target.type == NodeType.EXTERNAL_SYSTEM:
        return RelationshipType.CALLS
    if target.type == NodeType.CACHE:
        return RelationshipType.READS_FROM
    if target.type == NodeType.QUEUE:
        return RelationshipType.PUBLISHES
    return RelationshipType.ROUTES_TO


def _extract_unknowns(lowered: str) -> list[str]:
    unknowns: list[str] = []
    if "auth" not in lowered and "oauth" not in lowered and "login" not in lowered:
        unknowns.append("Authentication boundary is not described.")
    if "monitor" not in lowered and "observability" not in lowered and "trace" not in lowered:
        unknowns.append("Observability strategy is not described.")
    if "backup" not in lowered and "disaster" not in lowered and "recovery" not in lowered:
        unknowns.append("Disaster recovery strategy is not described.")
    return unknowns


def _extract_constraints(lowered: str) -> list[str]:
    constraints: list[str] = []
    if "single instance" in lowered:
        constraints.append("Database deployment is described as single instance.")
    if "single availability zone" in lowered or "single az" in lowered:
        constraints.append("Database deployment is described as single Availability Zone.")
    if "retention: 7 days" in lowered or "retention 7 days" in lowered:
        constraints.append("Backup retention is described as 7 days.")
    if "single container" in lowered:
        constraints.append("One or more services are described as single-container deployments.")
    return constraints


def _dedupe_edges(edges: list[ArchitectureEdge]) -> list[ArchitectureEdge]:
    seen: set[tuple[str, str, str]] = set()
    unique: list[ArchitectureEdge] = []
    for edge in edges:
        key = (edge.from_node, edge.to_node, edge.relationship)
        if key in seen:
            continue
        seen.add(key)
        unique.append(edge)
    return unique


def _mentions_in_order(
    sentence: str,
    nodes_by_alias: dict[str, ArchitectureNode],
) -> list[ArchitectureNode]:
    matches: list[tuple[int, int, ArchitectureNode]] = []
    for alias, node in nodes_by_alias.items():
        for match in re.finditer(_alias_pattern(alias), sentence):
            matches.append((match.start(), match.end(), node))

    matches.sort(key=lambda item: (item[0], -(item[1] - item[0])))
    accepted: list[tuple[int, int, ArchitectureNode]] = []
    for start, end, node in matches:
        if any(start < existing_end and end > existing_start for existing_start, existing_end, _ in accepted):
            continue
        accepted.append((start, end, node))

    return _collapse_repeated_nodes([node for _, _, node in accepted])


def _collapse_repeated_nodes(nodes: list[ArchitectureNode]) -> list[ArchitectureNode]:
    compacted: list[ArchitectureNode] = []
    for node in nodes:
        if compacted and compacted[-1].id == node.id:
            continue
        compacted.append(node)
    return compacted


def _contains_alias(text: str, alias: str) -> bool:
    return bool(re.search(_alias_pattern(alias), text))


def _alias_pattern(alias: str) -> str:
    escaped = re.escape(alias).replace(r"\ ", r"\s+")
    return rf"(?<![a-z0-9]){escaped}(?![a-z0-9])"


def _extract_named_components(lowered: str) -> list[str]:
    pattern = re.compile(
        r"\b([a-z][a-z0-9]*(?:\s+[a-z][a-z0-9]*){0,3}\s+"
        r"(?:service|api|gateway|bucket|database|nodes|node))\b"
    )
    ignored = {
        "db database",
        "prod db database",
        "single container",
        "single instance",
        "single availability zone",
    }
    names: list[str] = []
    for match in pattern.finditer(lowered):
        name = match.group(1)
        if name in ignored or name.startswith("single "):
            continue
        if name.endswith(" db database"):
            continue
        if name not in names:
            names.append(name)
    return names


def _infer_node_type(name: str) -> NodeType:
    if "database" in name or "bucket" in name:
        return NodeType.DATA_STORE
    if "api" in name and "stripe" in name:
        return NodeType.EXTERNAL_SYSTEM
    if "nodes" in name or "node" in name:
        return NodeType.EXTERNAL_SYSTEM
    return NodeType.SERVICE


def _display_name(name: str) -> str:
    words = []
    for word in name.split():
        if word in {"api", "s3", "db", "gpu"}:
            words.append(word.upper())
        elif word == "postgresql":
            words.append("PostgreSQL")
        else:
            words.append(word.title())
    return " ".join(words)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
