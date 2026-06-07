from pydantic import BaseModel, Field

from openarchitect.core.contracts.model_provider import ModelProvider
from openarchitect.core.schemas import ADR, ArchitectureDecision
from openarchitect.modules.adr.service import generate_adrs


class ADRsOutput(BaseModel):
    adrs: list[ADR] = Field(default_factory=list)


async def generate_adrs_with_llm(
    decisions: list[ArchitectureDecision],
    model_provider: ModelProvider,
) -> list[ADR]:
    if not decisions:
        return []

    prompt = f"""
You are an architecture governance assistant.
Generate proposed Architecture Decision Records from these decisions.

Rules:
- Use IDs ADR-001, ADR-002, etc.
- Status must be Proposed.
- Context must explain the concrete problem and evidence.
- Alternatives must be meaningful.
- Consequences must include benefits and tradeoffs.
- Preserve linked findings and diagram changes.

Decisions JSON:
{[decision.model_dump() for decision in decisions]}
"""
    output = await model_provider.generate_structured(prompt, ADRsOutput)
    if len(output.adrs) != len(decisions):
        return generate_adrs(decisions)

    adrs_by_title = {adr.title: adr for adr in output.adrs}
    formatted = generate_adrs(decisions)
    return [adrs_by_title.get(adr.title, adr) for adr in formatted]
