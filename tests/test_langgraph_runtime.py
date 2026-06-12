import asyncio
from typing import Any

from pydantic import BaseModel

from openarchitect.core.contracts.model_provider import ModelProvider
from openarchitect.core.schemas import (
    ADR,
    ArchitectureDecision,
    ArchitectureEdge,
    ArchitectureGraph,
    ArchitectureNode,
    NodeType,
    RelationshipType,
    ReviewFinding,
    Severity,
)
from openarchitect.runtime.langgraph.workflow import _run_llm_review_graph


class FakeModelProvider(ModelProvider):
    def __init__(self) -> None:
        self.prompts: list[str] = []
        self.schemas: list[str] = []

    @property
    def metadata(self) -> dict[str, Any]:
        return {"provider": "fake"}

    async def generate_text(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return """
{
  "architecture": {
    "nodes": [
      {
        "id": "api_gateway",
        "name": "API Gateway",
        "type": "service",
        "evidence": ["API Gateway"],
        "attributes": {}
      },
      {
        "id": "payments_service",
        "name": "Payments Service",
        "type": "service",
        "evidence": ["Payments Service"],
        "attributes": {}
      }
    ],
    "edges": [
      {
        "from": "api_gateway",
        "to": "payments_service",
        "relationship": "routes_to",
        "evidence": ["API Gateway -> Payments Service"]
      }
    ],
    "constraints": [],
    "unknowns": []
  }
}
"""

    async def generate_structured(
        self,
        prompt: str,
        schema: type[BaseModel],
    ) -> BaseModel:
        self.prompts.append(prompt)
        self.schemas.append(schema.__name__)

        if schema.__name__ == "ArchitectureGraphOutput":
            return schema(
                architecture=ArchitectureGraph(
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
                    ],
                    edges=[
                        ArchitectureEdge(
                            **{
                                "from": "api_gateway",
                                "to": "payments_service",
                                "relationship": RelationshipType.ROUTES_TO,
                                "evidence": ["API Gateway -> Payments Service"],
                            }
                        )
                    ],
                )
            )

        if schema.__name__ == "ReviewFindingsOutput":
            role = _role_from_prompt(prompt)
            finding_id = role.lower().split()[0] + "-001"
            return schema(
                findings=[
                    ReviewFinding(
                        id=finding_id,
                        agent_role=role,
                        severity=Severity.HIGH,
                        finding=f"{role} finding",
                        evidence=["API Gateway -> Payments Service"],
                        affected_components=["payments-service"],
                        recommendation=f"{role} recommendation",
                        requires_adr=True,
                    )
                ]
            )

        if schema.__name__ == "GraphCriticPatchOutput":
            return schema()

        if schema.__name__ == "FindingCoveragePatchOutput":
            return schema()

        if schema.__name__ == "LeadArchitectOutput":
            return schema(
                findings=[
                    ReviewFinding(
                        id="lead-001",
                        agent_role="Lead Architect",
                        severity=Severity.HIGH,
                        finding="Consolidated finding",
                        evidence=["API Gateway -> Payments Service"],
                        affected_components=["payments-service"],
                        recommendation="Consolidated recommendation",
                        requires_adr=True,
                    )
                ],
                decisions=[
                    ArchitectureDecision(
                        id="decision-001",
                        title="Consolidated Architecture Decision",
                        context="Consolidated context",
                        decision="Consolidated decision",
                        alternatives=["Keep current design"],
                        consequences=["Clearer design tradeoff"],
                        impacted_components=["payments-service"],
                        linked_finding_ids=["lead-001"],
                        diagram_changes=["Update diagram"],
                    )
                ],
            )

        if schema.__name__ == "ADRsOutput":
            raise AssertionError("ADR generation should be decision-bound, not LLM-bound")

        if schema.__name__ == "ArchitectureV2PatchOutput":
            return schema()

        raise AssertionError(f"Unexpected schema {schema.__name__}")


def test_llm_langgraph_runs_parallel_pillar_reviewers_and_lead_architect() -> None:
    provider = FakeModelProvider()

    state = asyncio.run(
        _run_llm_review_graph(
            "Architecture Flow: API Gateway -> Payments Service.",
            provider,
        )
    )

    assert provider.schemas.count("ReviewFindingsOutput") == 6
    assert any("Operational Excellence Reviewer" in prompt for prompt in provider.prompts)
    assert any("Security Reviewer" in prompt for prompt in provider.prompts)
    assert any("Reliability Reviewer" in prompt for prompt in provider.prompts)
    assert any("Performance Efficiency Reviewer" in prompt for prompt in provider.prompts)
    assert any("Cost Optimization Reviewer" in prompt for prompt in provider.prompts)
    assert any("Sustainability Reviewer" in prompt for prompt in provider.prompts)
    assert "FindingCoveragePatchOutput" in provider.schemas
    assert "LeadArchitectOutput" in provider.schemas
    assert "ArchitectureV2PatchOutput" in provider.schemas
    assert set(state["reviewed_pillars"]) == {
        "operational_excellence",
        "security",
        "reliability",
        "performance_efficiency",
        "cost_optimization",
        "sustainability",
    }
    assert state["findings"][0].agent_role == "Lead Architect"
    assert state["decisions"][0].linked_finding_ids == ["lead-001"]
    assert state["adrs"][0].id == "ADR-001"
    assert state["adrs"][0].linked_findings == ["lead-001"]
    assert state["diagram"].format == "mermaid"


def _role_from_prompt(prompt: str) -> str:
    for role in (
        "Operational Excellence Reviewer",
        "Security Reviewer",
        "Reliability Reviewer",
        "Performance Efficiency Reviewer",
        "Cost Optimization Reviewer",
        "Sustainability Reviewer",
    ):
        if role in prompt:
            return role
    return "Unknown Architect"
