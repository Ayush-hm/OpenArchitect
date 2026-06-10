from dataclasses import dataclass

from openarchitect.core.schemas import ArchitectureDecision, ArchitectureGraph, ReviewFinding, Severity


@dataclass(frozen=True)
class ValidationIssue:
    field: str
    message: str


def validate_and_repair_findings(
    findings: list[ReviewFinding],
    graph: ArchitectureGraph,
) -> list[ReviewFinding]:
    component_refs = _component_refs(graph)
    repaired: list[ReviewFinding] = []
    seen_ids: set[str] = set()

    for finding in findings:
        if finding.id in seen_ids:
            continue
        finding.affected_components = _normalize_component_list(
            finding.affected_components,
            component_refs,
        )
        repaired.append(finding)
        seen_ids.add(finding.id)

    return repaired


def validate_and_repair_decisions(
    decisions: list[ArchitectureDecision],
    findings: list[ReviewFinding],
    graph: ArchitectureGraph,
) -> tuple[list[ArchitectureDecision], list[ValidationIssue]]:
    finding_ids = {finding.id for finding in findings}
    findings_by_id = {finding.id: finding for finding in findings}
    component_refs = _component_refs(graph)
    valid_decisions: list[ArchitectureDecision] = []
    issues: list[ValidationIssue] = []
    seen_ids: set[str] = set()

    for decision in decisions:
        if decision.id in seen_ids:
            issues.append(ValidationIssue("id", f"Duplicate decision id '{decision.id}' was dropped."))
            continue
        seen_ids.add(decision.id)

        original_links = list(decision.linked_finding_ids)
        decision.linked_finding_ids = [
            finding_id for finding_id in decision.linked_finding_ids if finding_id in finding_ids
        ]
        missing_links = sorted(set(original_links) - set(decision.linked_finding_ids))
        for finding_id in missing_links:
            issues.append(
                ValidationIssue(
                    "linked_finding_ids",
                    f"Decision '{decision.id}' referenced missing finding '{finding_id}'.",
                )
            )

        if not decision.linked_finding_ids:
            issues.append(
                ValidationIssue(
                    "linked_finding_ids",
                    f"Decision '{decision.id}' was dropped because it has no valid linked findings.",
                )
            )
            continue

        linked_components = [
            component
            for finding_id in decision.linked_finding_ids
            for component in findings_by_id[finding_id].affected_components
        ]
        decision.impacted_components = _normalize_component_list(
            [*decision.impacted_components, *linked_components],
            component_refs,
        )
        if not decision.impacted_components:
            issues.append(
                ValidationIssue(
                    "impacted_components",
                    f"Decision '{decision.id}' was dropped because no impacted components matched the graph.",
                )
            )
            continue

        if not decision.diagram_changes:
            decision.diagram_changes = [f"Update architecture diagram for: {decision.title}."]

        valid_decisions.append(decision)

    return valid_decisions, issues


def validate_decision_coverage(
    findings: list[ReviewFinding],
    decisions: list[ArchitectureDecision],
) -> list[ValidationIssue]:
    covered_finding_ids = {
        finding_id
        for decision in decisions
        for finding_id in decision.linked_finding_ids
    }
    issues: list[ValidationIssue] = []

    for finding in findings:
        if not _must_be_decision_covered(finding):
            continue
        if finding.id in covered_finding_ids:
            continue
        issues.append(
            ValidationIssue(
                "decision_coverage",
                f"Finding '{finding.id}' is {finding.severity} and requires_adr=true "
                "but is not covered by any validated decision.",
            )
        )

    return issues


def downgrade_uncovered_adr_findings(
    findings: list[ReviewFinding],
    decisions: list[ArchitectureDecision],
) -> list[ReviewFinding]:
    covered_finding_ids = {
        finding_id
        for decision in decisions
        for finding_id in decision.linked_finding_ids
    }
    downgraded: list[ReviewFinding] = []

    for finding in findings:
        if _must_be_decision_covered(finding) and finding.id not in covered_finding_ids:
            finding = finding.model_copy(deep=True)
            finding.requires_adr = False
            rationale = (
                "ADR not generated: no validated architecture decision was selected for "
                "this finding, so it remains a review follow-up instead of an ADR-backed decision."
            )
            if rationale not in finding.recommendation:
                finding.recommendation = f"{finding.recommendation.rstrip()} {rationale}"
        downgraded.append(finding)

    return downgraded


def _must_be_decision_covered(finding: ReviewFinding) -> bool:
    return finding.requires_adr and finding.severity in {Severity.HIGH, Severity.CRITICAL}


def _component_refs(graph: ArchitectureGraph) -> dict[str, str]:
    refs: dict[str, str] = {}
    for node in graph.nodes:
        refs[_normalize_ref(node.id)] = node.id
        refs[_normalize_ref(node.name)] = node.id
    return refs


def _normalize_component_list(
    components: list[str],
    component_refs: dict[str, str],
) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for component in components:
        node_id = component_refs.get(_normalize_ref(component))
        if node_id is None or node_id in seen:
            continue
        normalized.append(node_id)
        seen.add(node_id)
    return normalized


def _normalize_ref(value: str) -> str:
    return " ".join(value.replace("-", " ").replace("_", " ").lower().split())
