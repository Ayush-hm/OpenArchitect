from pydantic import BaseModel, Field

from openarchitect.core.contracts.model_provider import ModelProvider
from openarchitect.core.schemas import ArchitectureDecision, ArchitectureGraph, ReviewFinding
from openarchitect.modules.planning.validation import (
    downgrade_uncovered_adr_findings,
    validate_decision_coverage,
    validate_and_repair_decisions,
    validate_and_repair_findings,
)


class LeadArchitectOutput(BaseModel):
    findings: list[ReviewFinding] = Field(default_factory=list)
    decisions: list[ArchitectureDecision] = Field(default_factory=list)


async def consolidate_with_lead_architect_llm(
    graph: ArchitectureGraph,
    findings: list[ReviewFinding],
    model_provider: ModelProvider,
) -> LeadArchitectOutput:
    prompt = f"""
You are the Lead Architect agent.

Consolidate specialist review findings into a coherent architecture plan.

Responsibilities:
- Deduplicate overlapping findings.
- Resolve conflicts between reliability, security, scalability, and FinOps goals.
- Prioritize the most important findings.
- Decide which findings require ADRs.
- Create architecture decisions only for ADR-worthy findings.
- Preserve or rewrite finding IDs so linked decisions can reference them.

Rules:
- Do not invent findings that are not grounded in the provided graph or specialist findings.
- Security issues involving disabled encryption, public subnets, or tenant data isolation are ADR-worthy unless clearly trivial.
- Reliability issues involving single-AZ, single instance databases, missing DR, RTO, or RPO are ADR-worthy.
- Scalability issues involving no autoscaling under explicit load targets are ADR-worthy.
- FinOps issues are ADR-worthy when they affect architecture shape or operational policy.
- Each decision must include context, decision, alternatives, consequences, impacted components, linked finding IDs, and diagram changes.

Architecture graph JSON:
{graph.model_dump_json(by_alias=True)}

Specialist findings JSON:
{[finding.model_dump() for finding in findings]}
"""
    output = await model_provider.generate_structured(prompt, LeadArchitectOutput)
    repaired_findings = validate_and_repair_findings(output.findings, graph)
    repaired_decisions, issues = validate_and_repair_decisions(
        output.decisions,
        repaired_findings,
        graph,
    )
    coverage_issues = validate_decision_coverage(repaired_findings, repaired_decisions)
    issues = [*issues, *coverage_issues]
    if not issues:
        return LeadArchitectOutput(findings=repaired_findings, decisions=repaired_decisions)

    repair_prompt = f"""
The previous Lead Architect output failed contract validation.

Repair only the decisions and findings. Return valid structured output.

Validation issues:
{[issue.__dict__ for issue in issues]}

Rules:
- Every decision linked_finding_ids value must exist in the final findings list.
- Every impacted component must refer to a node id or node name in the architecture graph.
- Every high or critical finding with requires_adr=true must either be linked by
  at least one decision, or be downgraded to requires_adr=false with a clear
  rationale in the recommendation.
- Do not reference findings that are not present.
- Do not invent unrelated decisions.

Architecture graph JSON:
{graph.model_dump_json(by_alias=True)}

Previous findings JSON:
{[finding.model_dump() for finding in repaired_findings]}

Previous decisions JSON:
{[decision.model_dump() for decision in output.decisions]}
"""
    repaired_output = await model_provider.generate_structured(repair_prompt, LeadArchitectOutput)
    final_findings = validate_and_repair_findings(repaired_output.findings, graph)
    final_decisions, _ = validate_and_repair_decisions(
        repaired_output.decisions,
        final_findings,
        graph,
    )
    final_coverage_issues = validate_decision_coverage(final_findings, final_decisions)
    if final_coverage_issues:
        final_findings = downgrade_uncovered_adr_findings(final_findings, final_decisions)
    return LeadArchitectOutput(findings=final_findings, decisions=final_decisions)
