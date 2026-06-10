import asyncio
from typing import Any

from pydantic import BaseModel

from openarchitect.core.contracts.model_provider import ModelProvider
from openarchitect.core.schemas import ArchitectureEdge, ArchitectureGraph, ArchitectureNode, NodeType
from openarchitect.modules.extraction.critic_service import critique_architecture_graph


class GraphCriticFakeProvider(ModelProvider):
    @property
    def metadata(self) -> dict[str, Any]:
        return {"provider": "fake"}

    async def generate_text(self, prompt: str) -> str:
        raise AssertionError("Graph critic should use structured output")

    async def generate_structured(
        self,
        prompt: str,
        schema: type[BaseModel],
    ) -> BaseModel:
        assert schema.__name__ == "GraphCriticPatchOutput"
        return schema(
            add_nodes=[
                ArchitectureNode(
                    id="eks-cluster",
                    name="EKS Cluster",
                    type=NodeType.WORKER,
                    evidence=["Infrastructure Platform: Amazon EKS"],
                    attributes={"worker_nodes": "Two worker nodes"},
                )
            ],
            update_nodes=[
                {
                    "id": "eks-cluster",
                    "attributes": {"autoscaling": "Disabled"},
                    "evidence": ["Autoscaling: Disabled"],
                    "reason": "EKS autoscaling is explicitly described.",
                }
            ],
            remove_edges=[
                {
                    "from": "authentication-service",
                    "to": "internet",
                    "relationship": "depends_on",
                    "reason": "JWT generation evidence does not support dependency on internet.",
                }
            ],
        )


def test_graph_critic_applies_evidence_bound_patch() -> None:
    graph = ArchitectureGraph(
        nodes=[
            ArchitectureNode(
                id="internet",
                name="Internet",
                type=NodeType.USER,
                evidence=["Internet -> API Gateway"],
            ),
            ArchitectureNode(
                id="authentication-service",
                name="Authentication Service",
                type=NodeType.SERVICE,
                evidence=["Authentication Service Handles user login and JWT token generation."],
            ),
        ],
        edges=[
            ArchitectureEdge(
                **{
                    "from": "authentication-service",
                    "to": "internet",
                    "relationship": "depends_on",
                    "evidence": [
                        "Authentication Service Handles user login and JWT token generation."
                    ],
                }
            )
        ],
    )
    source = """
Infrastructure Platform: Amazon EKS
Worker nodes: Two worker nodes
Autoscaling: Disabled
Authentication Service Handles user login and JWT token generation.
Internet -> API Gateway
"""

    updated = asyncio.run(
        critique_architecture_graph(graph, source, GraphCriticFakeProvider())
    )

    assert "eks-cluster" in {node.id for node in updated.nodes}
    eks = next(node for node in updated.nodes if node.id == "eks-cluster")
    assert eks.attributes["autoscaling"] == "Disabled"
    assert updated.edges == []


def test_graph_critic_rejects_patch_without_source_evidence() -> None:
    class UnsupportedPatchProvider(GraphCriticFakeProvider):
        async def generate_structured(
            self,
            prompt: str,
            schema: type[BaseModel],
        ) -> BaseModel:
            return schema(
                add_nodes=[
                    ArchitectureNode(
                        id="redis",
                        name="Redis",
                        type=NodeType.CACHE,
                        evidence=["Redis cache"],
                    )
                ]
            )

    updated = asyncio.run(
        critique_architecture_graph(
            ArchitectureGraph(),
            "Architecture only mentions PostgreSQL.",
            UnsupportedPatchProvider(),
        )
    )

    assert updated.nodes == []
