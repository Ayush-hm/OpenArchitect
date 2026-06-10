from pydantic import BaseModel, Field

from openarchitect.core.schemas.adr import ADR
from openarchitect.core.schemas.architecture import ArchitectureGraph
from openarchitect.core.schemas.diagram import DiagramSpec
from openarchitect.core.schemas.review import ArchitectureDecision, ReviewFinding


class ArchitectureReviewRequest(BaseModel):
    document_text: str = Field(min_length=1)


class WorkflowResult(BaseModel):
    architecture_v1: ArchitectureGraph
    findings: list[ReviewFinding]
    decisions: list[ArchitectureDecision]
    adrs: list[ADR]
    architecture_v2: ArchitectureGraph
    diagram: DiagramSpec

