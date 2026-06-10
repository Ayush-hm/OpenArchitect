from pydantic import BaseModel, Field

from openarchitect.core.contracts.model_provider import ModelProvider
from openarchitect.core.schemas import ArchitectureDecision, ArchitectureGraph, ReviewFinding


class ArchitectureDecisionsOutput(BaseModel):
    decisions: list[ArchitectureDecision] = Field(default_factory=list)


async def plan_decisions_with_llm(
    graph: ArchitectureGraph,
    findings: list[ReviewFinding],
    model_provider: ModelProvider,
) -> list[ArchitectureDecision]:
    prompt = f"""
You are an architecture decision planner.
Turn ADR-worthy findings into proposed architecture decisions.

Rules:
- Combine duplicate findings into one decision when appropriate.
- Each decision must include context, decision, alternatives, consequences,
  impacted components, linked finding IDs, and diagram changes.
- Do not create ADRs for trivial documentation-only changes.
- Make tradeoffs explicit.

Architecture graph JSON:
{graph.model_dump_json(by_alias=True)}

Findings JSON:
{[finding.model_dump() for finding in findings]}
"""
    output = await model_provider.generate_structured(prompt, ArchitectureDecisionsOutput)
    return output.decisions

