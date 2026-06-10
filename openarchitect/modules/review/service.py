from openarchitect.core.schemas import ArchitectureGraph, ReviewFinding, Severity


def review_architecture(graph: ArchitectureGraph) -> list[ReviewFinding]:
    """Run deterministic specialist review checks for the first MVP loop."""
    findings: list[ReviewFinding] = []
    node_names = {node.name.lower(): node for node in graph.nodes}
    edge_text = " ".join(edge.description or "" for edge in graph.edges).lower()
    context_text = f"{edge_text} {' '.join(graph.constraints)}".lower()
    node_ids = {node.id for node in graph.nodes}

    if any("aurora" in name or "postgres" in name or "database" in name or name == "db" for name in node_names):
        if not any(node.type == "cache" for node in _values(graph)):
            findings.append(
                ReviewFinding(
                    id="scalability-001",
                    agent_role="Scalability Architect",
                    severity=Severity.HIGH,
                    finding="Read traffic appears to go directly to the primary data store without a cache layer.",
                    evidence=["Detected data store but no cache component."],
                    affected_components=_primary_data_store_names(graph),
                    recommendation="Introduce a cache for hot read paths.",
                    requires_adr=True,
                )
            )

    if "single instance" in context_text or "single availability zone" in context_text:
        findings.append(
            ReviewFinding(
                id="reliability-001",
                agent_role="Reliability Architect",
                severity=Severity.CRITICAL,
                finding="The primary database appears to run as a single instance in a single availability zone.",
                evidence=["SAD mentions single instance or single Availability Zone database deployment."],
                affected_components=_primary_data_store_names(graph),
                recommendation="Move the primary database to a highly available deployment with multi-AZ failover.",
                requires_adr=True,
            )
        )

    if "email service" in node_names and "synchronous" in edge_text:
        findings.append(
            ReviewFinding(
                id="reliability-002",
                agent_role="Reliability Architect",
                severity=Severity.HIGH,
                finding="Email delivery appears to be synchronous in the request path.",
                evidence=["Architecture text mentions synchronous Email Service calls."],
                affected_components=["Backend Api", "Email Service"],
                recommendation="Introduce a queue and worker for asynchronous email delivery.",
                requires_adr=True,
                )
            )

    if "shared-s3-bucket" in node_ids and "all-services" in node_ids:
        findings.append(
            ReviewFinding(
                id="security-002",
                agent_role="Security Architect",
                severity=Severity.HIGH,
                finding="A shared S3 bucket appears to be accessible by all services, creating broad blast radius and unclear data ownership.",
                evidence=["Architecture flow references Shared S3 Bucket used by All Services."],
                affected_components=["Shared S3 Bucket", "All Services"],
                recommendation="Replace the shared bucket pattern with service-owned buckets or scoped prefixes and least-privilege IAM policies.",
                requires_adr=True,
            )
        )

    if "fraud-detection-service" in node_ids and "gpu-nodes" in node_ids:
        findings.append(
            ReviewFinding(
                id="cost-001",
                agent_role="Cost Architect",
                severity=Severity.MEDIUM,
                finding="Fraud detection depends on GPU nodes, which may be expensive and operationally specialized.",
                evidence=["Architecture flow connects Fraud Detection Service to GPU Nodes."],
                affected_components=["Fraud Detection Service", "GPU Nodes"],
                recommendation="Introduce a dedicated fraud inference boundary with autoscaling and cost controls for GPU workloads.",
                requires_adr=True,
            )
        )

    if any("Authentication boundary" in unknown for unknown in graph.unknowns):
        findings.append(
            ReviewFinding(
                id="security-001",
                agent_role="Security Architect",
                severity=Severity.MEDIUM,
                finding="The architecture does not describe an authentication or ingress trust boundary.",
                evidence=["Extraction unknown: Authentication boundary is not described."],
                affected_components=[node.name for node in graph.nodes],
                recommendation="Document or introduce a clear ingress/authentication boundary.",
                requires_adr=True,
            )
        )

    if any("Observability strategy" in unknown for unknown in graph.unknowns):
        findings.append(
            ReviewFinding(
                id="operations-001",
                agent_role="Operations Architect",
                severity=Severity.MEDIUM,
                finding="The architecture does not describe observability for tracing, metrics, or alerting.",
                evidence=["Extraction unknown: Observability strategy is not described."],
                affected_components=[node.name for node in graph.nodes],
                recommendation="Add distributed tracing, metrics, logs, and alerting as first-class architecture concerns.",
                requires_adr=False,
            )
        )

    return findings


def _values(graph: ArchitectureGraph):
    return graph.nodes


def _primary_data_store_names(graph: ArchitectureGraph) -> list[str]:
    primary = [
        node.name
        for node in graph.nodes
        if node.type == "data_store" and "bucket" not in node.name.lower()
    ]
    return primary or [node.name for node in graph.nodes if node.type == "data_store"]
