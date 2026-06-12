import asyncio
from typing import Any

import pytest
from pydantic import BaseModel

from openarchitect.core.contracts.model_provider import ModelProvider
from openarchitect.core.schemas import (
    ArchitectureDecision,
    ArchitectureReviewRequest,
    ReviewFinding,
    Severity,
)
from openarchitect.workflow import run_review_workflow


class WorkflowFakeProvider(ModelProvider):
    @property
    def metadata(self) -> dict[str, Any]:
        return {"provider": "fake"}

    async def generate_text(self, prompt: str) -> str:
        return """
{
  "architecture": {
    "nodes": [
      {
        "id": "frontend",
        "name": "Frontend",
        "type": "service",
        "evidence": ["Frontend"],
        "attributes": {}
      },
      {
        "id": "backend-api",
        "name": "Backend API",
        "type": "service",
        "evidence": ["Backend API"],
        "attributes": {}
      },
      {
        "id": "aurora",
        "name": "Aurora",
        "type": "data_store",
        "evidence": ["Aurora"],
        "attributes": {}
      },
      {
        "id": "email-service",
        "name": "Email Service",
        "type": "external_system",
        "evidence": ["Email Service"],
        "attributes": {}
      }
    ],
    "edges": [
      {
        "from": "frontend",
        "to": "backend-api",
        "relationship": "calls",
        "evidence": ["Frontend calls Backend API"]
      },
      {
        "from": "backend-api",
        "to": "aurora",
        "relationship": "reads_from",
        "evidence": ["Backend API reads and writes Aurora"]
      },
      {
        "from": "backend-api",
        "to": "email-service",
        "relationship": "calls",
        "evidence": ["Backend API calls Email Service synchronously"]
      }
    ],
    "constraints": ["Backend API calls Email Service synchronously"],
    "unknowns": []
  }
}
"""

    async def generate_structured(
        self,
        prompt: str,
        schema: type[BaseModel],
    ) -> BaseModel:
        if schema.__name__ in {"GraphCriticPatchOutput", "FindingCoveragePatchOutput"}:
            return schema()

        if schema.__name__ == "ReviewFindingsOutput":
            return schema(
                findings=[
                    ReviewFinding(
                        id="reliability-001",
                        agent_role="Reliability Architect",
                        severity=Severity.HIGH,
                        finding="Email delivery is synchronous in the request path.",
                        evidence=["Backend API calls Email Service synchronously"],
                        affected_components=["backend-api", "email-service"],
                        recommendation="Move email delivery behind an asynchronous queue.",
                        requires_adr=True,
                    )
                ]
            )

        if schema.__name__ == "LeadArchitectOutput":
            return schema(
                findings=[
                    ReviewFinding(
                        id="lead-001",
                        agent_role="Lead Architect",
                        severity=Severity.HIGH,
                        finding="Email delivery is synchronous in the request path.",
                        evidence=["Backend API calls Email Service synchronously"],
                        affected_components=["backend-api", "email-service"],
                        recommendation="Introduce an asynchronous email workflow.",
                        requires_adr=True,
                    )
                ],
                decisions=[
                    ArchitectureDecision(
                        id="decision-001",
                        title="Introduce Asynchronous Email Workflow",
                        context="Backend API calls Email Service synchronously.",
                        decision="Place email work on a queue and process it with workers.",
                        alternatives=["Keep synchronous email calls"],
                        consequences=["Request handling is less coupled to email delivery"],
                        impacted_components=["backend-api", "email-service"],
                        linked_finding_ids=["lead-001"],
                        diagram_changes=["Add a queue-backed worker path for email delivery."],
                    )
                ],
            )

        if schema.__name__ == "ArchitectureV2PatchOutput":
            return schema(
                add_nodes=[
                    {
                        "id": "email-queue",
                        "name": "Email Queue",
                        "type": "queue",
                        "decision_ids": ["decision-001"],
                        "reason": "decision-001 introduces asynchronous email delivery.",
                    },
                    {
                        "id": "email-worker",
                        "name": "Email Worker",
                        "type": "worker",
                        "decision_ids": ["decision-001"],
                        "reason": "decision-001 processes email work outside the request path.",
                    },
                ],
                add_edges=[
                    {
                        "from": "backend-api",
                        "to": "email-queue",
                        "relationship": "publishes",
                        "decision_ids": ["decision-001"],
                        "reason": "Backend API publishes email jobs.",
                    },
                    {
                        "from": "email-queue",
                        "to": "email-worker",
                        "relationship": "subscribes_to",
                        "decision_ids": ["decision-001"],
                        "reason": "Email Worker consumes queued email jobs.",
                    },
                    {
                        "from": "email-worker",
                        "to": "email-service",
                        "relationship": "calls",
                        "decision_ids": ["decision-001"],
                        "reason": "Email Worker calls the external Email Service.",
                    },
                ],
            )

        raise AssertionError(f"Unexpected schema {schema.__name__}")


class FailingProvider(WorkflowFakeProvider):
    async def generate_text(self, prompt: str) -> str:
        raise RuntimeError("model unavailable")


def test_review_workflow_uses_llm_graph(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "openarchitect.workflow.architecture_review.create_model_provider",
        lambda: WorkflowFakeProvider(),
    )

    result = asyncio.run(
        run_review_workflow(
            ArchitectureReviewRequest(
                document_text=(
                    "Frontend calls Backend API. Backend API reads and writes Aurora. "
                    "Backend API calls Email Service synchronously."
                )
            )
        )
    )

    assert {node.id for node in result.architecture_v1.nodes} >= {
        "frontend",
        "backend-api",
        "aurora",
        "email-service",
    }
    assert result.findings[0].agent_role == "Lead Architect"
    assert result.decisions[0].linked_finding_ids == ["lead-001"]
    assert result.adrs[0].linked_findings == ["lead-001"]
    assert "email_queue" in result.diagram.content


def test_review_workflow_does_not_fall_back_to_rules(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "openarchitect.workflow.architecture_review.create_model_provider",
        lambda: FailingProvider(),
    )

    with pytest.raises(RuntimeError, match="model unavailable"):
        asyncio.run(
            run_review_workflow(
                ArchitectureReviewRequest(
                    document_text="Frontend calls Backend API. Backend API reads Aurora."
                )
            )
        )
