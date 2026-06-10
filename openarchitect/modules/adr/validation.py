from dataclasses import dataclass

from openarchitect.core.schemas import ADR, ArchitectureDecision, ArchitectureGraph, ReviewFinding


@dataclass(frozen=True)
class ADRValidationIssue:
    field: str
    message: str


def validate_adrs(
    adrs: list[ADR],
    decisions: list[ArchitectureDecision],
    findings: list[ReviewFinding],
    graph: ArchitectureGraph,
) -> tuple[list[ADR], list[ADRValidationIssue]]:
    finding_ids = {finding.id for finding in findings}
    component_ids = {node.id for node in graph.nodes}
    decision_titles = {decision.title for decision in decisions}
    valid: list[ADR] = []
    issues: list[ADRValidationIssue] = []

    for adr in adrs:
        if adr.title not in decision_titles:
            issues.append(
                ADRValidationIssue(
                    "title",
                    f"ADR '{adr.id}' was dropped because it does not come from a validated decision.",
                )
            )
            continue

        original_links = list(adr.linked_findings)
        adr.linked_findings = [finding_id for finding_id in adr.linked_findings if finding_id in finding_ids]
        for finding_id in sorted(set(original_links) - set(adr.linked_findings)):
            issues.append(
                ADRValidationIssue(
                    "linked_findings",
                    f"ADR '{adr.id}' referenced missing finding '{finding_id}'.",
                )
            )

        if not adr.linked_findings:
            issues.append(
                ADRValidationIssue(
                    "linked_findings",
                    f"ADR '{adr.id}' was dropped because it has no valid linked findings.",
                )
            )
            continue

        adr.impacted_components = [
            component for component in adr.impacted_components if component in component_ids
        ]
        if not adr.impacted_components:
            issues.append(
                ADRValidationIssue(
                    "impacted_components",
                    f"ADR '{adr.id}' was dropped because it has no graph-backed impacted components.",
                )
            )
            continue

        valid.append(adr)

    return valid, issues
