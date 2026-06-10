from pydantic import BaseModel, Field


class ADR(BaseModel):
    id: str
    title: str
    status: str = "Proposed"
    context: str
    decision: str
    alternatives: list[str] = Field(default_factory=list)
    consequences: list[str] = Field(default_factory=list)
    impacted_components: list[str] = Field(default_factory=list)
    linked_findings: list[str] = Field(default_factory=list)
    diagram_changes: list[str] = Field(default_factory=list)

    def to_markdown(self) -> str:
        alternatives = "\n".join(f"- {item}" for item in self.alternatives) or "- None recorded"
        consequences = "\n".join(f"- {item}" for item in self.consequences) or "- None recorded"
        impacted = "\n".join(f"- {item}" for item in self.impacted_components) or "- None recorded"
        linked = "\n".join(f"- {item}" for item in self.linked_findings) or "- None recorded"
        changes = "\n".join(f"- {item}" for item in self.diagram_changes) or "- None recorded"

        return (
            f"# {self.id}: {self.title}\n\n"
            f"Status: {self.status}\n\n"
            "## Context\n\n"
            f"{self.context}\n\n"
            "## Decision\n\n"
            f"{self.decision}\n\n"
            "## Alternatives Considered\n\n"
            f"{alternatives}\n\n"
            "## Consequences\n\n"
            f"{consequences}\n\n"
            "## Impacted Components\n\n"
            f"{impacted}\n\n"
            "## Linked Findings\n\n"
            f"{linked}\n\n"
            "## Diagram Changes\n\n"
            f"{changes}\n"
        )

