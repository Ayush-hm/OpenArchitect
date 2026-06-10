import asyncio
from typing import Any

from pydantic import BaseModel

from openarchitect.core.contracts.model_provider import ModelProvider
from openarchitect.core.schemas import (
    ADR,
    ArchitectureDecision,
    ArchitectureGraph,
    ArchitectureNode,
    NodeType,
)
from openarchitect.modules.diagram.v2_planner_service import plan_architecture_v2_with_llm


class V2PlannerFakeProvider(ModelProvider):
    @property
    def metadata(self) -> dict[str, Any]:
        return {"provider": "fake"}

    async def generate_text(self, prompt: str) -> str:
        raise AssertionError("v2 planner should use structured output")

    async def generate_structured(
        self,
        prompt: str,
        schema: type[BaseModel],
    ) -> BaseModel:
        assert schema.__name__ == "ArchitectureV2PatchOutput"
        return schema(
            update_nodes=[
                {
                    "id": "postgresql",
                    "name": "PostgreSQL / RDS Multi-AZ",
                    "attributes": {
                        "configuration": "Multi-AZ managed database",
                        "failover": "enabled",
                    },
                    "decision_ids": ["ADR-001"],
                    "reason": "ADR-001 migrates the database to Multi-AZ RDS.",
                },
                {
                    "id": "eks-cluster",
                    "attributes": {"autoscaling": "enabled"},
                    "decision_ids": ["ADR-002"],
                    "reason": "ADR-002 enables EKS autoscaling.",
                },
            ],
            remove_constraints=[
                {
                    "text": "Single instance for database",
                    "decision_ids": ["ADR-001"],
                    "reason": "Target database is no longer a single instance.",
                },
                {
                    "text": "Autoscaling disabled for EKS worker nodes",
                    "decision_ids": ["ADR-002"],
                    "reason": "Target EKS autoscaling is enabled.",
                },
            ],
            add_constraints=[
                {
                    "text": "Target database uses Multi-AZ managed failover",
                    "decision_ids": ["ADR-001"],
                    "reason": "Summarizes the target database decision.",
                }
            ],
        )


def test_architecture_v2_planner_applies_decision_backed_patch() -> None:
    graph = ArchitectureGraph(
        nodes=[
            ArchitectureNode(
                id="postgresql",
                name="PostgreSQL",
                type=NodeType.DATA_STORE,
                attributes={"configuration": "Single instance, Single Availability Zone"},
            ),
            ArchitectureNode(
                id="eks-cluster",
                name="Amazon EKS",
                type=NodeType.WORKER,
                attributes={"autoscaling": "disabled"},
            ),
        ],
        constraints=[
            "Single instance for database",
            "Autoscaling disabled for EKS worker nodes",
        ],
    )
    decisions = [
        ArchitectureDecision(
            id="ADR-001",
            title="Migrate to Multi-AZ Database",
            context="DB is single instance.",
            decision="Use Multi-AZ RDS.",
            impacted_components=["postgresql"],
            linked_finding_ids=["REL-001"],
        ),
        ArchitectureDecision(
            id="ADR-002",
            title="Enable EKS Autoscaling",
            context="Autoscaling is disabled.",
            decision="Enable autoscaling.",
            impacted_components=["eks-cluster"],
            linked_finding_ids=["SCAL-001"],
        ),
    ]
    adrs = [
        ADR(
            id=decision.id,
            title=decision.title,
            context=decision.context,
            decision=decision.decision,
            impacted_components=decision.impacted_components,
            linked_findings=decision.linked_finding_ids,
        )
        for decision in decisions
    ]

    updated = asyncio.run(
        plan_architecture_v2_with_llm(graph, decisions, adrs, V2PlannerFakeProvider())
    )

    postgresql = next(node for node in updated.nodes if node.id == "postgresql")
    eks = next(node for node in updated.nodes if node.id == "eks-cluster")

    assert postgresql.name == "PostgreSQL / RDS Multi-AZ"
    assert postgresql.attributes["configuration"] == "Multi-AZ managed database"
    assert eks.attributes["autoscaling"] == "enabled"
    assert "Single instance for database" not in updated.constraints
    assert "Autoscaling disabled for EKS worker nodes" not in updated.constraints
    assert "Target database uses Multi-AZ managed failover" in updated.constraints


def test_architecture_v2_planner_rejects_patch_without_valid_decision() -> None:
    class UnsupportedV2PlannerProvider(V2PlannerFakeProvider):
        async def generate_structured(
            self,
            prompt: str,
            schema: type[BaseModel],
        ) -> BaseModel:
            return schema(
                add_nodes=[
                    {
                        "id": "redis",
                        "name": "Redis",
                        "type": "cache",
                        "decision_ids": ["ADR-999"],
                        "reason": "Unsupported decision id.",
                    }
                ]
            )

    graph = ArchitectureGraph(
        nodes=[ArchitectureNode(id="postgresql", name="PostgreSQL", type=NodeType.DATA_STORE)]
    )
    decisions = [
        ArchitectureDecision(
            id="ADR-001",
            title="Migrate Database",
            context="Context",
            decision="Decision",
            impacted_components=["postgresql"],
            linked_finding_ids=["REL-001"],
        )
    ]

    updated = asyncio.run(
        plan_architecture_v2_with_llm(graph, decisions, [], UnsupportedV2PlannerProvider())
    )

    assert {node.id for node in updated.nodes} == {"postgresql"}


def test_architecture_v2_planner_cleans_stale_constraints_when_target_state_contradicts_them() -> None:
    class CleanupV2PlannerProvider(V2PlannerFakeProvider):
        async def generate_structured(
            self,
            prompt: str,
            schema: type[BaseModel],
        ) -> BaseModel:
            return schema(
                update_nodes=[
                    {
                        "id": "postgresql",
                        "attributes": {"configuration": "Multi-AZ deployment"},
                        "decision_ids": ["ADR-001"],
                        "reason": "ADR-001 changes the database to Multi-AZ.",
                    }
                ],
                add_constraints=[
                    {
                        "text": "Multi-AZ deployment for database",
                        "decision_ids": ["ADR-001"],
                        "reason": "Target database state.",
                    }
                ],
            )

    graph = ArchitectureGraph(
        nodes=[ArchitectureNode(id="postgresql", name="PostgreSQL", type=NodeType.DATA_STORE)],
        constraints=[
            "Single instance for database",
            "Database encryption disabled",
        ],
    )
    decisions = [
        ArchitectureDecision(
            id="ADR-001",
            title="Database High Availability",
            context="Database is single instance.",
            decision="Use Multi-AZ database deployment.",
            impacted_components=["postgresql"],
            linked_finding_ids=["REL-001"],
        )
    ]

    updated = asyncio.run(
        plan_architecture_v2_with_llm(graph, decisions, [], CleanupV2PlannerProvider())
    )

    assert "Single instance for database" not in updated.constraints
    assert "Database encryption disabled" in updated.constraints
    assert "Multi-AZ deployment for database" in updated.constraints
