import os
from dataclasses import dataclass


@dataclass(frozen=True)
class PillarProfile:
    id: str
    name: str
    reviewer_role: str
    description: str
    review_focus: tuple[str, ...]
    required_unknowns: tuple[str, ...]
    adr_triggers: tuple[str, ...]
    severity_guidance: tuple[str, ...]


@dataclass(frozen=True)
class FrameworkProfile:
    id: str
    name: str
    pillars: tuple[PillarProfile, ...]


AWS_WELL_ARCHITECTED_PROFILE = FrameworkProfile(
    id="aws_well_architected",
    name="AWS Well-Architected Framework",
    pillars=(
        PillarProfile(
            id="operational_excellence",
            name="Operational Excellence",
            reviewer_role="Operational Excellence Reviewer",
            description="Evaluate the ability to operate, observe, deploy, and continuously improve the workload.",
            review_focus=(
                "observability, metrics, logs, tracing, alerting, and dashboards",
                "deployment safety, rollback strategy, change management, and automation",
                "incident response, runbooks, ownership, and operational readiness",
                "continuous improvement loops and operational feedback",
            ),
            required_unknowns=(
                "observability strategy",
                "deployment and rollback process",
                "incident response and runbook ownership",
                "operational SLOs or health indicators",
            ),
            adr_triggers=(
                "new observability platform or telemetry architecture",
                "material deployment strategy change",
                "operational ownership or incident-management boundary",
            ),
            severity_guidance=(
                "critical when missing operations posture can hide or prolong severe outages",
                "high when deployment or observability gaps create material production risk",
                "medium for unclear ownership, runbooks, or improvement loops",
            ),
        ),
        PillarProfile(
            id="security",
            name="Security",
            reviewer_role="Security Reviewer",
            description="Evaluate confidentiality, integrity, identity, access, detection, and data protection controls.",
            review_focus=(
                "identity, authentication, authorization, and least privilege",
                "network exposure, trust boundaries, ingress, and segmentation",
                "encryption, key management, secrets, and data classification",
                "threat detection, audit logging, compliance, and tenant isolation",
            ),
            required_unknowns=(
                "data classification",
                "authentication and authorization boundary",
                "encryption in transit and at rest",
                "secrets management",
                "audit logging and threat detection",
            ),
            adr_triggers=(
                "central authentication or ingress boundary",
                "encryption or key-management architecture",
                "tenant/data isolation model",
                "service-to-service access model",
            ),
            severity_guidance=(
                "critical for public exposure of sensitive data or missing primary access controls",
                "high for weak trust boundaries, disabled encryption, or broad shared access",
                "medium for incomplete auditability or unclear data ownership",
            ),
        ),
        PillarProfile(
            id="reliability",
            name="Reliability",
            reviewer_role="Reliability Reviewer",
            description="Evaluate workload resiliency, fault tolerance, recovery, and service continuity.",
            review_focus=(
                "availability targets, SLOs, RTO, RPO, backups, and restore testing",
                "single points of failure, multi-AZ or regional resiliency, and failover",
                "retry, timeout, backpressure, queueing, and graceful degradation",
                "capacity limits, dependency failure modes, and disaster recovery",
            ),
            required_unknowns=(
                "availability target or SLO",
                "RTO and RPO",
                "backup and restore testing",
                "failover strategy",
                "dependency failure handling",
            ),
            adr_triggers=(
                "database high availability or failover architecture",
                "disaster recovery strategy",
                "async decoupling for critical workflows",
                "multi-region or multi-AZ target state",
            ),
            severity_guidance=(
                "critical for explicit single points of failure in critical paths",
                "high for missing DR, RTO/RPO, failover, or backup restore strategy",
                "medium for unclear retry, timeout, or graceful degradation behavior",
            ),
        ),
        PillarProfile(
            id="performance_efficiency",
            name="Performance Efficiency",
            reviewer_role="Performance Efficiency Reviewer",
            description="Evaluate whether resources, scaling patterns, and architecture choices match workload demand.",
            review_focus=(
                "load targets, latency targets, throughput, and bottlenecks",
                "horizontal scaling, autoscaling, caching, and partitioning",
                "managed service fit, right technology choice, and workload-specific resource shape",
                "performance testing, capacity planning, and continuous performance monitoring",
            ),
            required_unknowns=(
                "load and latency targets",
                "autoscaling policy",
                "performance testing approach",
                "capacity limits and bottlenecks",
            ),
            adr_triggers=(
                "caching architecture",
                "autoscaling or compute architecture change",
                "database read/write scaling strategy",
                "queueing or partitioning for throughput",
            ),
            severity_guidance=(
                "critical when stated load cannot plausibly be served by the architecture",
                "high for missing autoscaling or clear bottlenecks under explicit demand",
                "medium for unclear load testing, capacity, or monitoring posture",
            ),
        ),
        PillarProfile(
            id="cost_optimization",
            name="Cost Optimization",
            reviewer_role="Cost Optimization Reviewer",
            description="Evaluate whether spend is understood, controlled, and aligned to business value.",
            review_focus=(
                "cost visibility, ownership, budgets, alerts, and tagging",
                "right sizing, elasticity, managed service economics, and waste reduction",
                "expensive specialized resources such as GPU, high IOPS, or always-on capacity",
                "tradeoffs between reliability, performance, and cost",
            ),
            required_unknowns=(
                "budget or cost guardrails",
                "cost allocation/tagging model",
                "right-sizing or autoscaling policy",
                "expensive resource utilization",
            ),
            adr_triggers=(
                "major managed-service or compute-shape decision",
                "GPU or specialized resource isolation/scaling boundary",
                "cost-control policy that changes architecture shape",
            ),
            severity_guidance=(
                "high for unconstrained expensive capacity or missing cost guardrails on major workloads",
                "medium for unclear ownership, tagging, budget, or utilization model",
                "low for incremental optimization opportunities",
            ),
        ),
        PillarProfile(
            id="sustainability",
            name="Sustainability",
            reviewer_role="Sustainability Reviewer",
            description="Evaluate environmental efficiency through resource reduction, utilization, and lifecycle choices.",
            review_focus=(
                "resource utilization, idle capacity, autoscaling, and data lifecycle management",
                "storage retention, data movement, and compute efficiency",
                "region/service choices when sustainability requirements are stated",
                "measurement and continuous improvement of environmental impact",
            ),
            required_unknowns=(
                "resource utilization and idle-capacity posture",
                "data retention and lifecycle policy",
                "sustainability requirements or constraints",
                "measurement approach for efficiency improvements",
            ),
            adr_triggers=(
                "data retention or lifecycle architecture",
                "region or deployment model driven by sustainability constraints",
                "material compute/storage efficiency architecture change",
            ),
            severity_guidance=(
                "high when explicit sustainability goals are contradicted by architecture choices",
                "medium for major wasteful capacity, retention, or data movement patterns",
                "low when requirements are absent but efficiency improvements are available",
            ),
        ),
    ),
)


SUPPORTED_FRAMEWORKS = {
    AWS_WELL_ARCHITECTED_PROFILE.id: AWS_WELL_ARCHITECTED_PROFILE,
    "aws": AWS_WELL_ARCHITECTED_PROFILE,
}


def get_framework_profile(profile_id: str | None = None) -> FrameworkProfile:
    selected = (profile_id or os.getenv("OPENARCHITECT_REVIEW_FRAMEWORK") or "aws").strip().lower()
    try:
        return SUPPORTED_FRAMEWORKS[selected]
    except KeyError as exc:
        supported = ", ".join(sorted(SUPPORTED_FRAMEWORKS))
        raise RuntimeError(
            f"Unsupported review framework '{selected}'. Supported frameworks: {supported}."
        ) from exc
