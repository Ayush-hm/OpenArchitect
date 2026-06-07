from pydantic import BaseModel, Field

from openarchitect.core.contracts.model_provider import ModelProvider
from openarchitect.core.schemas import ArchitectureGraph, ReviewFinding


class ReviewFindingsOutput(BaseModel):
    findings: list[ReviewFinding] = Field(default_factory=list)


async def review_architecture_with_llm(
    graph: ArchitectureGraph,
    model_provider: ModelProvider,
) -> list[ReviewFinding]:
    prompt = f"""
You are a multi-agent architecture review board.
Review the architecture graph as four specialist agents:
- Scalability Architect
- Reliability Architect
- Security Architect
- Cost Architect

Generate concrete review findings. Each finding must cite evidence from the graph,
constraints, or unknowns. Mark requires_adr=true only for meaningful architectural
decisions such as database HA, caching, async messaging, storage ownership,
security boundary, GPU inference boundary, or DR strategy.

Avoid generic advice. Prefer 3 to 7 high-value findings.

Architecture graph JSON:
{graph.model_dump_json(by_alias=True)}
"""
    output = await model_provider.generate_structured(prompt, ReviewFindingsOutput)
    return output.findings


async def review_architecture_as_specialist_with_llm(
    graph: ArchitectureGraph,
    model_provider: ModelProvider,
    specialist_role: str,
) -> list[ReviewFinding]:
    prompt = f"""
You are the {specialist_role} in a multi-agent architecture review board.

Review only from your specialist perspective. Generate concrete findings with
evidence from nodes, edges, constraints, or unknowns. Avoid generic advice.
Mark requires_adr=true only when the recommendation requires an architectural
decision with meaningful tradeoffs.

Expected focus:
- Scalability Architect: load, throughput, caching, autoscaling, bottlenecks
- Reliability Architect: HA, DR, failover, retries, single points of failure
- Security Architect: trust boundaries, encryption, public exposure, tenant isolation
- FinOps Architect: overprovisioning, managed service cost, scaling efficiency

Return only findings from the {specialist_role} perspective.

Architecture graph JSON:
{graph.model_dump_json(by_alias=True)}
"""
    output = await model_provider.generate_structured(prompt, ReviewFindingsOutput)
    return output.findings
