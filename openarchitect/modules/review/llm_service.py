from typing import Any

from pydantic import BaseModel, Field

from openarchitect.core.contracts.model_provider import ModelProvider
from openarchitect.core.schemas import ArchitectureGraph, ReviewFinding
from openarchitect.modules.review.frameworks import (
    AWS_WELL_ARCHITECTED_PROFILE,
    FrameworkProfile,
    PillarProfile,
)
from openarchitect.observability import traceable_step


class ReviewFindingsOutput(BaseModel):
    findings: list[ReviewFinding] = Field(default_factory=list)


@traceable_step(name="Review Architecture With Framework", run_type="chain")
async def review_architecture_with_llm(
    graph: ArchitectureGraph,
    model_provider: ModelProvider,
) -> list[ReviewFinding]:
    findings: list[ReviewFinding] = []
    for pillar in AWS_WELL_ARCHITECTED_PROFILE.pillars:
        findings.extend(
            await review_architecture_for_pillar_with_llm(
                graph,
                model_provider,
                AWS_WELL_ARCHITECTED_PROFILE,
                pillar,
            )
        )
    return findings


@traceable_step(name="Legacy Specialist Review", run_type="chain")
async def review_architecture_as_specialist_with_llm(
    graph: ArchitectureGraph,
    model_provider: ModelProvider,
    specialist_role: str,
) -> list[ReviewFinding]:
    pillar = _pillar_for_legacy_role(specialist_role)
    if pillar is not None:
        return await review_architecture_for_pillar_with_llm(
            graph,
            model_provider,
            AWS_WELL_ARCHITECTED_PROFILE,
            pillar,
        )

    prompt = f"""
You are the {specialist_role} in a multi-agent architecture review board.

Review only from your specialist perspective. Generate concrete findings with
evidence from nodes, edges, constraints, or unknowns. Avoid generic advice.
Mark requires_adr=true only when the recommendation requires an architectural
decision with meaningful tradeoffs.

Expected focus:
- Stay within the requested specialist perspective.
- Prefer evidence-backed risks over generic best-practice advice.
- Call out unknowns when missing information materially affects the review.

Return only findings from the {specialist_role} perspective.

Architecture graph JSON:
{graph.model_dump_json(by_alias=True)}
"""
    output = await model_provider.generate_structured(prompt, ReviewFindingsOutput)
    return output.findings


@traceable_step(name="AWS Pillar Review", run_type="chain")
async def review_architecture_for_pillar_with_llm(
    graph: ArchitectureGraph,
    model_provider: ModelProvider,
    framework: FrameworkProfile,
    pillar: PillarProfile,
    langsmith_extra: dict[str, Any] | None = None,
) -> list[ReviewFinding]:
    prompt = f"""
You are the {pillar.reviewer_role} for the {framework.name}.

Review only this pillar:
- Pillar id: {pillar.id}
- Pillar name: {pillar.name}
- Description: {pillar.description}

Review focus:
{_bullet_list(pillar.review_focus)}

Important unknowns to surface when absent or unclear:
{_bullet_list(pillar.required_unknowns)}

ADR-worthy triggers for this pillar:
{_bullet_list(pillar.adr_triggers)}

Severity guidance:
{_bullet_list(pillar.severity_guidance)}

Rules:
- Generate concrete findings with evidence from nodes, edges, constraints,
  unknowns, attributes, or cited evidence.
- Do not add generic best-practice advice that is not tied to the graph.
- If a risk depends on missing information, make the missing information explicit
  in assumption_or_unknown.
- Set framework="{framework.id}" and pillar="{pillar.id}" on every finding.
- Set agent_role="{pillar.reviewer_role}" on every finding.
- Set risk_area to a short concern name, such as "encryption", "failover",
  "autoscaling", "observability", "cost guardrails", or "data lifecycle".
- Mark requires_adr=true only when the recommendation changes architecture
  shape or material operational policy.

Architecture graph JSON:
{graph.model_dump_json(by_alias=True)}
"""
    output = await model_provider.generate_structured(prompt, ReviewFindingsOutput)
    return [_stamp_finding(finding, framework, pillar) for finding in output.findings]


def _stamp_finding(
    finding: ReviewFinding,
    framework: FrameworkProfile,
    pillar: PillarProfile,
) -> ReviewFinding:
    finding.framework = framework.id
    finding.pillar = pillar.id
    finding.agent_role = pillar.reviewer_role
    return finding


def _bullet_list(items: tuple[str, ...]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _pillar_for_legacy_role(role: str) -> PillarProfile | None:
    normalized = role.strip().lower()
    legacy_map = {
        "scalability architect": "performance_efficiency",
        "performance efficiency reviewer": "performance_efficiency",
        "reliability architect": "reliability",
        "reliability reviewer": "reliability",
        "security architect": "security",
        "security reviewer": "security",
        "cost architect": "cost_optimization",
        "finops architect": "cost_optimization",
        "cost optimization reviewer": "cost_optimization",
        "operational excellence reviewer": "operational_excellence",
        "sustainability reviewer": "sustainability",
    }
    pillar_id = legacy_map.get(normalized)
    if pillar_id is None:
        return None
    return next(
        pillar
        for pillar in AWS_WELL_ARCHITECTED_PROFILE.pillars
        if pillar.id == pillar_id
    )
