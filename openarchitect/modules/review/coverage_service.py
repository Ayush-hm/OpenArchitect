import re

from pydantic import BaseModel, Field

from openarchitect.core.contracts.model_provider import ModelProvider
from openarchitect.core.schemas import ArchitectureGraph, ReviewFinding, Severity
from openarchitect.modules.review.frameworks import (
    AWS_WELL_ARCHITECTED_PROFILE,
    FrameworkProfile,
)
from openarchitect.observability import traceable_step


class FindingRemovalPatch(BaseModel):
    id: str
    reason: str


class FindingUpdatePatch(BaseModel):
    id: str
    framework: str | None = None
    pillar: str | None = None
    risk_area: str | None = None
    severity: Severity | None = None
    finding: str | None = None
    evidence: list[str] = Field(default_factory=list)
    affected_components: list[str] = Field(default_factory=list)
    assumption_or_unknown: str | None = None
    recommendation: str | None = None
    requires_adr: bool | None = None
    reason: str


class FindingCoveragePatchOutput(BaseModel):
    add_findings: list[ReviewFinding] = Field(default_factory=list)
    update_findings: list[FindingUpdatePatch] = Field(default_factory=list)
    remove_findings: list[FindingRemovalPatch] = Field(default_factory=list)


@traceable_step(name="Finding Coverage Critic", run_type="chain")
async def critique_finding_coverage(
    graph: ArchitectureGraph,
    findings: list[ReviewFinding],
    model_provider: ModelProvider,
    framework: FrameworkProfile = AWS_WELL_ARCHITECTED_PROFILE,
    reviewed_pillar_ids: list[str] | None = None,
) -> list[ReviewFinding]:
    reviewed_pillar_ids = reviewed_pillar_ids or sorted(
        {finding.pillar for finding in findings if finding.pillar}
    )
    prompt = f"""
You are the OpenArchitect Finding Coverage Critic.

Review whether the specialist findings adequately cover material risks already
present in the architecture graph. Return a minimal findings patch.

Review framework: {framework.name}
Expected pillars:
{_pillar_summary(framework)}

Reviewed pillar ids:
{reviewed_pillar_ids}

Use the configured framework as the review contract. Check that all expected
pillars were reviewed and that findings cover material risks already visible in
the graph, including:
- Operational excellence: observability, deployment safety, incident response,
  runbooks, ownership, and continuous improvement.
- Security: data protection, identity, access, encryption, network exposure,
  trust boundaries, tenant isolation, logging, and compliance.
- Reliability: availability, failover, backup, disaster recovery, RTO/RPO,
  dependency failure, retries, and graceful degradation.
- Performance efficiency: load targets, bottlenecks, autoscaling, caching,
  capacity, and performance testing.
- Cost optimization: budgets, cost allocation, right sizing, elasticity,
  specialized expensive resources, and waste.
- Sustainability: resource utilization, idle capacity, data lifecycle,
  storage retention, and efficiency measurement.

Rules:
- Add findings only when they are grounded in graph nodes, edges, constraints,
  unknowns, attributes, or evidence.
- Do not add generic best-practice advice that is not tied to the graph.
- Update or remove only findings that are unsupported, duplicated, or incorrectly
  scoped.
- Use graph node ids or node names for affected_components.
- Set framework="{framework.id}" and a valid pillar id on added findings.
- Use assumption_or_unknown when a finding is based on missing information.
- Keep the patch minimal.

Architecture graph JSON:
{graph.model_dump_json(by_alias=True)}

Current findings JSON:
{[finding.model_dump() for finding in findings]}
"""
    try:
        patch = await model_provider.generate_structured(prompt, FindingCoveragePatchOutput)
    except Exception:
        return findings
    return apply_finding_coverage_patch(graph, findings, patch, framework)


def apply_finding_coverage_patch(
    graph: ArchitectureGraph,
    findings: list[ReviewFinding],
    patch: FindingCoveragePatchOutput,
    framework: FrameworkProfile = AWS_WELL_ARCHITECTED_PROFILE,
) -> list[ReviewFinding]:
    graph_context = _graph_context(graph)
    component_refs = _component_refs(graph)
    valid_pillars = {pillar.id for pillar in framework.pillars}
    current = {finding.id: finding.model_copy(deep=True) for finding in findings}

    for removal in patch.remove_findings:
        if removal.reason.strip():
            current.pop(removal.id, None)

    for update in patch.update_findings:
        finding = current.get(update.id)
        if finding is None or not update.reason.strip():
            continue
        if update.evidence and not _evidence_supported(update.evidence, graph_context):
            continue

        if update.severity is not None:
            finding.severity = update.severity
        if update.framework:
            finding.framework = update.framework
        if update.pillar and update.pillar in valid_pillars:
            finding.pillar = update.pillar
        if update.risk_area:
            finding.risk_area = update.risk_area
        if update.finding:
            finding.finding = update.finding
        if update.evidence:
            finding.evidence = _dedupe_text([*finding.evidence, *update.evidence])
        if update.affected_components:
            finding.affected_components = _normalize_components(
                [*finding.affected_components, *update.affected_components],
                component_refs,
            )
        if update.assumption_or_unknown:
            finding.assumption_or_unknown = update.assumption_or_unknown
        if update.recommendation:
            finding.recommendation = update.recommendation
        if update.requires_adr is not None:
            finding.requires_adr = update.requires_adr

    for finding in patch.add_findings:
        if finding.id in current:
            continue
        if finding.pillar and finding.pillar not in valid_pillars:
            continue
        if finding.framework is None:
            finding.framework = framework.id
        if not _evidence_supported(finding.evidence, graph_context):
            continue
        finding.affected_components = _normalize_components(
            finding.affected_components,
            component_refs,
        )
        if not finding.affected_components:
            continue
        current[finding.id] = finding

    return list(current.values())


def _pillar_summary(framework: FrameworkProfile) -> str:
    return "\n".join(
        f"- {pillar.id}: {pillar.name} ({pillar.reviewer_role})"
        for pillar in framework.pillars
    )


def _graph_context(graph: ArchitectureGraph) -> str:
    parts: list[str] = []
    for node in graph.nodes:
        parts.extend([node.id, node.name, str(node.type), *node.evidence])
        parts.extend(f"{key}: {value}" for key, value in node.attributes.items())
    for edge in graph.edges:
        parts.extend([edge.from_node, edge.to_node, str(edge.relationship), *(edge.evidence or [])])
        if edge.description:
            parts.append(edge.description)
    parts.extend(graph.constraints)
    parts.extend(graph.unknowns)
    return _normalize_text(" ".join(parts))


def _component_refs(graph: ArchitectureGraph) -> dict[str, str]:
    refs: dict[str, str] = {}
    for node in graph.nodes:
        refs[_normalize_ref(node.id)] = node.id
        refs[_normalize_ref(node.name)] = node.id
    return refs


def _normalize_components(
    components: list[str],
    refs: dict[str, str],
) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for component in components:
        node_id = refs.get(_normalize_ref(component))
        if node_id is None or node_id in seen:
            continue
        normalized.append(node_id)
        seen.add(node_id)
    return normalized


def _evidence_supported(evidence: list[str], graph_context: str) -> bool:
    for item in evidence:
        normalized = _normalize_text(item)
        if not normalized:
            continue
        if normalized in graph_context:
            return True
        terms = _significant_terms(normalized)
        if terms and sum(1 for term in terms if term in graph_context) >= min(2, len(terms)):
            return True
    return False


def _dedupe_text(items: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for item in items:
        key = _normalize_text(item)
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def _normalize_ref(value: str) -> str:
    return " ".join(value.replace("-", " ").replace("_", " ").lower().split())


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value.lower())).strip()


def _significant_terms(value: str) -> list[str]:
    generic = {
        "architecture",
        "component",
        "components",
        "constraint",
        "current",
        "evidence",
        "finding",
        "service",
        "services",
    }
    return [
        term
        for term in re.findall(r"[a-z0-9]+", value)
        if len(term) > 2 and term not in generic
    ]
