import re

from openarchitect.core.schemas import ArchitectureEdge, ArchitectureGraph, ArchitectureNode


def validate_architecture_graph(
    graph: ArchitectureGraph,
    source_text: str,
    require_evidence: bool = True,
) -> ArchitectureGraph:
    normalized_source = _normalize(source_text)
    id_map: dict[str, str] = {}
    nodes: list[ArchitectureNode] = []
    for node in graph.nodes:
        if require_evidence and not _has_source_evidence(node.name, node.evidence, normalized_source):
            continue
        original_id = node.id
        normalized_node = _normalize_node(node)
        id_map[original_id] = normalized_node.id
        nodes.append(normalized_node)

    node_ids = {node.id for node in nodes}
    normalized_edges = [_normalize_edge(edge, id_map) for edge in graph.edges]

    edges = [
        edge
        for edge in normalized_edges
        if edge.from_node in node_ids
        and edge.to_node in node_ids
        and (not require_evidence or _has_edge_evidence(edge, nodes, normalized_source))
    ]

    return ArchitectureGraph(
        nodes=_dedupe_nodes(nodes),
        edges=_dedupe_edges(edges),
        constraints=graph.constraints,
        unknowns=graph.unknowns,
    )


def _normalize_node(node: ArchitectureNode) -> ArchitectureNode:
    node.id = _slug(node.id or node.name)
    return node


def _normalize_edge(edge: ArchitectureEdge, id_map: dict[str, str]) -> ArchitectureEdge:
    edge.from_node = id_map.get(edge.from_node, _slug(edge.from_node))
    edge.to_node = id_map.get(edge.to_node, _slug(edge.to_node))
    return edge


def _has_source_evidence(
    node_name: str,
    evidence: list[str],
    normalized_source: str,
) -> bool:
    if _normalize(node_name) in normalized_source:
        return True
    if any(term in normalized_source for term in _significant_terms(node_name)):
        return True
    return any(_normalize(item) in normalized_source for item in evidence if item.strip())


def _has_edge_evidence(
    edge: ArchitectureEdge,
    nodes: list[ArchitectureNode],
    normalized_source: str,
) -> bool:
    if any(_normalize(item) in normalized_source for item in edge.evidence if item.strip()):
        return True

    names_by_id = {node.id: node.name for node in nodes}
    from_name = _normalize(names_by_id.get(edge.from_node, edge.from_node))
    to_name = _normalize(names_by_id.get(edge.to_node, edge.to_node))
    return from_name in normalized_source and to_name in normalized_source


def _dedupe_nodes(nodes: list[ArchitectureNode]) -> list[ArchitectureNode]:
    seen: set[str] = set()
    unique: list[ArchitectureNode] = []
    for node in nodes:
        if node.id in seen:
            continue
        seen.add(node.id)
        unique.append(node)
    return unique


def _dedupe_edges(edges: list[ArchitectureEdge]) -> list[ArchitectureEdge]:
    seen: set[tuple[str, str, str]] = set()
    unique: list[ArchitectureEdge] = []
    for edge in edges:
        key = (edge.from_node, edge.to_node, str(edge.relationship))
        if key in seen:
            continue
        seen.add(key)
        unique.append(edge)
    return unique


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()


def _significant_terms(value: str) -> list[str]:
    generic = {
        "api",
        "bucket",
        "data",
        "database",
        "external",
        "node",
        "nodes",
        "service",
        "store",
        "system",
    }
    terms = re.findall(r"[a-z0-9]+", value.lower())
    return [term for term in terms if len(term) > 2 and term not in generic]
