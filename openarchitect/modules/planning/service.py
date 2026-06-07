from openarchitect.core.schemas import ArchitectureDecision, ReviewFinding


def plan_decisions(findings: list[ReviewFinding]) -> list[ArchitectureDecision]:
    """Turn ADR-worthy findings into proposed architecture decisions."""
    decisions: list[ArchitectureDecision] = []
    adr_findings = [finding for finding in findings if finding.requires_adr]

    for index, finding in enumerate(adr_findings, start=1):
        decision_id = f"decision-{index:03d}"
        decisions.append(
            ArchitectureDecision(
                id=decision_id,
                title=_title_for_finding(finding),
                context=finding.finding,
                decision=finding.recommendation,
                alternatives=_alternatives_for_finding(finding.id),
                consequences=_consequences_for_finding(finding.id),
                impacted_components=finding.affected_components,
                linked_finding_ids=[finding.id],
                diagram_changes=_diagram_changes_for_finding(finding.id),
            )
        )

    return decisions


def _title_for_finding(finding: ReviewFinding) -> str:
    if finding.id.startswith("scalability"):
        return "Introduce Cache For Hot Read Paths"
    if finding.id == "reliability-001":
        return "Move Primary Database To Multi-AZ Deployment"
    if finding.id.startswith("reliability"):
        return "Introduce Queue For Asynchronous Workflows"
    if finding.id == "security-002":
        return "Replace Shared S3 Bucket With Service-Scoped Storage"
    if finding.id.startswith("cost"):
        return "Create Dedicated Autoscaled Fraud Inference Boundary"
    if finding.id.startswith("security"):
        return "Define Centralized Ingress Authentication Boundary"
    return finding.recommendation.rstrip(".")


def _alternatives_for_finding(finding_id: str) -> list[str]:
    if finding_id.startswith("scalability"):
        return ["Scale the primary database", "Add read replicas", "Introduce a dedicated cache"]
    if finding_id == "reliability-001":
        return ["Keep single-AZ database", "Use read replicas only", "Adopt multi-AZ primary database failover"]
    if finding_id.startswith("reliability"):
        return ["Keep synchronous calls", "Use scheduled batch processing", "Introduce queue and worker"]
    if finding_id == "security-002":
        return ["Keep one shared bucket", "Use shared bucket with scoped prefixes", "Use service-owned buckets with least-privilege IAM"]
    if finding_id.startswith("cost"):
        return ["Keep GPU nodes directly coupled", "Use managed inference endpoint", "Use autoscaled dedicated GPU inference workers"]
    if finding_id.startswith("security"):
        return ["Per-service authentication", "Centralized API Gateway authentication", "External identity-aware proxy"]
    return ["Keep current architecture", "Apply recommended change"]


def _consequences_for_finding(finding_id: str) -> list[str]:
    if finding_id.startswith("scalability"):
        return ["Reduced read latency", "Lower database pressure", "Added cache invalidation complexity"]
    if finding_id == "reliability-001":
        return ["Improved availability during AZ failure", "Reduced database single point of failure", "Higher database cost and failover testing responsibility"]
    if finding_id.startswith("reliability"):
        return ["Reduced request-path coupling", "Improved retry handling", "Added queue operations responsibility"]
    if finding_id == "security-002":
        return ["Reduced blast radius for object storage access", "Clearer data ownership", "Requires IAM and storage migration planning"]
    if finding_id.startswith("cost"):
        return ["Improved GPU cost visibility", "Cleaner scaling boundary for inference workloads", "Requires workload-specific monitoring and capacity policy"]
    if finding_id.startswith("security"):
        return ["Clearer trust boundary", "More consistent access control", "Requires gateway or identity policy ownership"]
    return ["Improves architecture quality", "Requires implementation and operational follow-up"]


def _diagram_changes_for_finding(finding_id: str) -> list[str]:
    if finding_id.startswith("scalability"):
        return ["Add Redis cache between API and primary database."]
    if finding_id == "reliability-001":
        return ["Mark PostgreSQL Database as multi-AZ/high-availability deployment."]
    if finding_id.startswith("reliability"):
        return ["Add queue and worker between API and external email service."]
    if finding_id == "security-002":
        return ["Replace All Services to Shared S3 Bucket dependency with service-scoped storage boundaries."]
    if finding_id.startswith("cost"):
        return ["Add an autoscaled fraud inference boundary between Fraud Detection Service and GPU capacity."]
    if finding_id.startswith("security"):
        return ["Add API Gateway as the centralized ingress boundary."]
    return ["Update architecture diagram to reflect the proposed decision."]
