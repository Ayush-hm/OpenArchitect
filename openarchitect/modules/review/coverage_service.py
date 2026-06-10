import re

from pydantic import BaseModel, Field

from openarchitect.core.contracts.model_provider import ModelProvider
from openarchitect.core.schemas import ArchitectureGraph, ReviewFinding, Severity


class FindingRemovalPatch(BaseModel):
    id: str
    reason: str


class FindingUpdatePatch(BaseModel):
    id: str
    severity: Severity | None = None
    finding: str | None = None
    evidence: list[str] = Field(default_factory=list)
    affected_components: list[str] = Field(default_factory=list)
    recommendation: str | None = None
    requires_adr: bool | None = None
    reason: str


class FindingCoveragePatchOutput(BaseModel):
    add_findings: list[ReviewFinding] = Field(default_factory=list)
    update_findings: list[FindingUpdatePatch] = Field(default_factory=list)
    remove_findings: list[FindingRemovalPatch] = Field(default_factory=list)


async def critique_finding_coverage(
    graph: ArchitectureGraph,
    findings: list[ReviewFinding],
    model_provider: ModelProvider,
) -> list[ReviewFinding]:
    prompt = f"""
You are the OpenArchitect Finding Coverage Critic.

Review whether the specialist findings adequately cover material risks already
present in the architecture graph. Return a minimal findings patch.

This is not a PayFlow-specific rule system. Use general architecture review
principles:
- Data protection posture for sensitive data stores.
- Network exposure and trust boundaries.
- Availability, failover, backup, disaster recovery, RTO/RPO posture.
- Scaling posture for compute and stateful components.
- Access isolation for shared storage or shared infrastructure.
- Cost and operational tradeoffs when a risk changes architecture shape.

Rules:
- Add findings only when they are grounded in graph nodes, edges, constraints,
  unknowns, attributes, or evidence.
- Do not add generic best-practice advice that is not tied to the graph.
- Update or remove only findings that are unsupported, duplicated, or incorrectly
  scoped.
- Use graph node ids or node names for affected_components.
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
    return apply_finding_coverage_patch(graph, findings, patch)


def apply_finding_coverage_patch(
    graph: ArchitectureGraph,
    findings: list[ReviewFinding],
    patch: FindingCoveragePatchOutput,
) -> list[ReviewFinding]:
    graph_context = _graph_context(graph)
    component_refs = _component_refs(graph)
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
        if update.finding:
            finding.finding = update.finding
        if update.evidence:
            finding.evidence = _dedupe_text([*finding.evidence, *update.evidence])
        if update.affected_components:
            finding.affected_components = _normalize_components(
                [*finding.affected_components, *update.affected_components],
                component_refs,
            )
        if update.recommendation:
            finding.recommendation = update.recommendation
        if update.requires_adr is not None:
            finding.requires_adr = update.requires_adr

    for finding in patch.add_findings:
        if finding.id in current:
            continue
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
