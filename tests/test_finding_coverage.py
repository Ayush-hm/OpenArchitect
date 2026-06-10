import asyncio
from typing import Any

from pydantic import BaseModel

from openarchitect.core.contracts.model_provider import ModelProvider
from openarchitect.core.schemas import (
    ArchitectureGraph,
    ArchitectureNode,
    NodeType,
    ReviewFinding,
    Severity,
)
from openarchitect.modules.review.coverage_service import critique_finding_coverage


class CoverageFakeProvider(ModelProvider):
    @property
    def metadata(self) -> dict[str, Any]:
        return {"provider": "fake"}

    async def generate_text(self, prompt: str) -> str:
        raise AssertionError("Coverage critic should use structured output")

    async def generate_structured(
        self,
        prompt: str,
        schema: type[BaseModel],
    ) -> BaseModel:
        assert schema.__name__ == "FindingCoveragePatchOutput"
        return schema(
            add_findings=[
                ReviewFinding(
                    id="SEC-ENCRYPTION-001",
                    agent_role="Finding Coverage Critic",
                    severity=Severity.CRITICAL,
                    finding="Data stores do not have encryption at rest enabled.",
                    evidence=[
                        "Database encryption disabled",
                        "S3 encryption disabled",
                    ],
                    affected_components=["PostgreSQL", "S3 Bucket"],
                    recommendation="Enable encryption at rest for all sensitive data stores.",
                    requires_adr=True,
                )
            ]
        )


def test_finding_coverage_adds_supported_missing_finding() -> None:
    graph = ArchitectureGraph(
        nodes=[
            ArchitectureNode(id="postgresql", name="PostgreSQL", type=NodeType.DATA_STORE),
            ArchitectureNode(id="s3-bucket", name="S3 Bucket", type=NodeType.DATA_STORE),
        ],
        constraints=[
            "Database encryption disabled",
            "S3 encryption disabled",
        ],
    )

    findings = asyncio.run(
        critique_finding_coverage(graph, [], CoverageFakeProvider())
    )

    assert [finding.id for finding in findings] == ["SEC-ENCRYPTION-001"]
    assert findings[0].affected_components == ["postgresql", "s3-bucket"]


def test_finding_coverage_rejects_unsupported_finding() -> None:
    class UnsupportedCoverageProvider(CoverageFakeProvider):
        async def generate_structured(
            self,
            prompt: str,
            schema: type[BaseModel],
        ) -> BaseModel:
            return schema(
                add_findings=[
                    ReviewFinding(
                        id="SEC-UNSUPPORTED",
                        agent_role="Finding Coverage Critic",
                        severity=Severity.HIGH,
                        finding="Redis is not encrypted.",
                        evidence=["Redis encryption disabled"],
                        affected_components=["PostgreSQL"],
                        recommendation="Enable Redis encryption.",
                        requires_adr=True,
                    )
                ]
            )

    graph = ArchitectureGraph(
        nodes=[ArchitectureNode(id="postgresql", name="PostgreSQL", type=NodeType.DATA_STORE)]
    )

    findings = asyncio.run(
        critique_finding_coverage(graph, [], UnsupportedCoverageProvider())
    )

    assert findings == []
