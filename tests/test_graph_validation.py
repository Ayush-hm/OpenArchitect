from openarchitect.core.schemas import (
    ArchitectureEdge,
    ArchitectureGraph,
    ArchitectureNode,
    NodeType,
    RelationshipType,
)
from openarchitect.modules.extraction.validation import validate_architecture_graph


def test_validator_filters_unsupported_nodes_and_rewrites_edge_ids() -> None:
    graph = ArchitectureGraph(
        nodes=[
            ArchitectureNode(
                id="api_gateway",
                name="API Gateway",
                type=NodeType.SERVICE,
                evidence=["API Gateway"],
            ),
            ArchitectureNode(
                id="payments_service",
                name="Payments Service",
                type=NodeType.SERVICE,
                evidence=["Payments Service"],
            ),
            ArchitectureNode(
                id="gpu_nodes",
                name="GPU Nodes",
                type=NodeType.WORKER,
                evidence=["GPU Nodes"],
            ),
        ],
        edges=[
            ArchitectureEdge(
                **{
                    "from": "api_gateway",
                    "to": "payments_service",
                    "relationship": RelationshipType.ROUTES_TO,
                    "evidence": ["API Gateway -> Payments Service"],
                }
            ),
            ArchitectureEdge(
                **{
                    "from": "payments_service",
                    "to": "gpu_nodes",
                    "relationship": RelationshipType.USES,
                    "evidence": ["Payments Service -> GPU Nodes"],
                }
            ),
        ],
    )

    validated = validate_architecture_graph(
        graph,
        "Architecture Flow: API Gateway -> Payments Service.",
    )

    assert {node.id for node in validated.nodes} == {"api-gateway", "payments-service"}
    assert [(edge.from_node, edge.to_node) for edge in validated.edges] == [
        ("api-gateway", "payments-service")
    ]


def test_relationship_type_rejects_unknown_labels() -> None:
    edge = ArchitectureEdge(
        **{
            "from": "api",
            "to": "db",
            "relationship": "reads_from_cache",
        }
    )

    assert edge.relationship == RelationshipType.DEPENDS_ON
