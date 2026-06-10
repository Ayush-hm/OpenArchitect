import asyncio
import os

from openarchitect.core.schemas import ArchitectureReviewRequest
from openarchitect.workflow import run_review_workflow


def test_architecture_review_generates_adrs_and_diagram() -> None:
    os.environ["OPENARCHITECT_ALLOW_RULE_FALLBACK"] = "1"
    result = asyncio.run(
        run_review_workflow(
            ArchitectureReviewRequest(
                document_text=(
                    "Frontend calls Backend API. Backend API reads and writes Aurora. "
                    "Backend API calls Email Service synchronously."
                )
            )
        )
    )

    assert result.architecture_v1.nodes
    assert result.findings
    assert result.adrs
    assert result.diagram.format == "mermaid"
    assert "flowchart LR" in result.diagram.content


def test_payflow_sad_flow_extracts_named_services_and_risks() -> None:
    os.environ["OPENARCHITECT_ALLOW_RULE_FALLBACK"] = "1"
    result = asyncio.run(
        run_review_workflow(
            ArchitectureReviewRequest(
                document_text=(
                    "Architecture Flow: Internet -> API Gateway -> Authentication Service -> "
                    "Payments Service -> PostgreSQL. Payments Service -> Stripe API. "
                    "Reporting Service -> PostgreSQL. Fraud Detection Service -> GPU Nodes. "
                    "Shared S3 Bucket <- All Services. Database Deployment: Single instance "
                    "Single Availability Zone. Backups: Daily backups Retention: 7 days."
                )
            )
        )
    )

    node_ids = {node.id for node in result.architecture_v1.nodes}
    finding_ids = {finding.id for finding in result.findings}
    adr_titles = {adr.title for adr in result.adrs}

    assert "payments-service" in node_ids
    assert "stripe-api" in node_ids
    assert "postgresql-database" in node_ids
    assert "database" not in node_ids
    assert "db" not in node_ids
    assert "db-database" not in node_ids
    assert "reliability-001" in finding_ids
    assert "security-002" in finding_ids
    assert "cost-001" in finding_ids
    assert "Move Primary Database To Multi-AZ Deployment" in adr_titles
    assert "Replace Shared S3 Bucket With Service-Scoped Storage" in adr_titles
    assert "Create Dedicated Autoscaled Fraud Inference Boundary" in adr_titles
    assert "all_services -->|stores_in| shared_s3_bucket" in result.diagram.content
