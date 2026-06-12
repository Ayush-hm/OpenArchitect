from enum import StrEnum

from pydantic import BaseModel, Field


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ReviewFinding(BaseModel):
    id: str
    agent_role: str
    framework: str | None = None
    pillar: str | None = None
    risk_area: str | None = None
    severity: Severity
    finding: str
    evidence: list[str] = Field(default_factory=list)
    affected_components: list[str] = Field(default_factory=list)
    assumption_or_unknown: str | None = None
    recommendation: str
    requires_adr: bool = False


class ImprovementProposal(BaseModel):
    id: str
    title: str
    summary: str
    source_finding_ids: list[str] = Field(default_factory=list)
    affected_components: list[str] = Field(default_factory=list)
    requires_adr: bool = True


class ArchitectureDecision(BaseModel):
    id: str
    title: str
    context: str
    decision: str
    alternatives: list[str] = Field(default_factory=list)
    consequences: list[str] = Field(default_factory=list)
    impacted_components: list[str] = Field(default_factory=list)
    linked_finding_ids: list[str] = Field(default_factory=list)
    diagram_changes: list[str] = Field(default_factory=list)
