from openarchitect.core.schemas import (
    ADR,
    ArchitectureDecision,
    ArchitectureGraph,
    ArchitectureNode,
    NodeType,
    ReviewFinding,
    Severity,
)
from openarchitect.modules.adr.service import generate_adrs
from openarchitect.modules.adr.validation import validate_adrs
from openarchitect.modules.planning.validation import (
    downgrade_uncovered_adr_findings,
    validate_and_repair_decisions,
    validate_decision_coverage,
)


def test_decision_validation_drops_missing_finding_links_and_normalizes_components() -> None:
    graph = ArchitectureGraph(
        nodes=[
            ArchitectureNode(id="eks-cluster", name="Amazon EKS", type=NodeType.WORKER),
            ArchitectureNode(id="postgresql", name="PostgreSQL", type=NodeType.DATA_STORE),
        ]
    )
    findings = [
        ReviewFinding(
            id="SCAL-001",
            agent_role="Lead Architect",
            severity=Severity.HIGH,
            finding="Autoscaling is disabled.",
            evidence=["Autoscaling disabled"],
            affected_components=["Amazon EKS"],
            recommendation="Enable autoscaling.",
            requires_adr=True,
        )
    ]
    decisions = [
        ArchitectureDecision(
            id="ADR-001",
            title="Enable EKS Autoscaling",
            context="Autoscaling is disabled.",
            decision="Enable autoscaling.",
            impacted_components=["Amazon EKS"],
            linked_finding_ids=["SCAL-001", "FIN-001"],
        )
    ]

    valid, issues = validate_and_repair_decisions(decisions, findings, graph)

    assert valid[0].linked_finding_ids == ["SCAL-001"]
    assert valid[0].impacted_components == ["eks-cluster"]
    assert any("FIN-001" in issue.message for issue in issues)


def test_adr_validation_keeps_only_decision_bound_graph_backed_adrs() -> None:
    graph = ArchitectureGraph(
        nodes=[ArchitectureNode(id="postgresql", name="PostgreSQL", type=NodeType.DATA_STORE)]
    )
    findings = [
        ReviewFinding(
            id="REL-001",
            agent_role="Lead Architect",
            severity=Severity.CRITICAL,
            finding="Database is single AZ.",
            evidence=["Single Availability Zone"],
            affected_components=["postgresql"],
            recommendation="Use Multi-AZ.",
            requires_adr=True,
        )
    ]
    decisions = [
        ArchitectureDecision(
            id="ADR-001",
            title="Migrate to Multi-AZ Database",
            context="Database is single AZ.",
            decision="Use Multi-AZ.",
            impacted_components=["postgresql"],
            linked_finding_ids=["REL-001"],
        )
    ]
    adrs = [
        *generate_adrs(decisions),
        ADR(
            id="ADR-999",
            title="Generic API Gateway Decision",
            context="Generic context",
            decision="Add gateway",
            impacted_components=["postgresql"],
            linked_findings=["REL-001"],
        ),
    ]

    valid, issues = validate_adrs(adrs, decisions, findings, graph)

    assert [adr.id for adr in valid] == ["ADR-001"]
    assert any("does not come from a validated decision" in issue.message for issue in issues)


def test_decision_coverage_flags_high_adr_finding_without_decision() -> None:
    findings = [
        ReviewFinding(
            id="REL-003",
            agent_role="Lead Architect",
            severity=Severity.HIGH,
            finding="No disaster recovery strategy is defined.",
            evidence=["No disaster recovery plan"],
            affected_components=["postgresql"],
            recommendation="Define DR strategy.",
            requires_adr=True,
        )
    ]

    issues = validate_decision_coverage(findings, [])

    assert len(issues) == 1
    assert "REL-003" in issues[0].message


def test_uncovered_adr_findings_are_explicitly_downgraded() -> None:
    findings = [
        ReviewFinding(
            id="REL-003",
            agent_role="Lead Architect",
            severity=Severity.CRITICAL,
            finding="No disaster recovery strategy is defined.",
            evidence=["No disaster recovery plan"],
            affected_components=["postgresql"],
            recommendation="Define DR strategy.",
            requires_adr=True,
        )
    ]

    downgraded = downgrade_uncovered_adr_findings(findings, [])

    assert downgraded[0].requires_adr is False
    assert "ADR not generated" in downgraded[0].recommendation
