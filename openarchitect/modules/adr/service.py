from openarchitect.core.schemas import ADR, ArchitectureDecision


def generate_adrs(decisions: list[ArchitectureDecision]) -> list[ADR]:
    return [
        ADR(
            id=f"ADR-{index:03d}",
            title=decision.title,
            context=decision.context,
            decision=decision.decision,
            alternatives=decision.alternatives,
            consequences=decision.consequences,
            impacted_components=decision.impacted_components,
            linked_findings=decision.linked_finding_ids,
            diagram_changes=decision.diagram_changes,
        )
        for index, decision in enumerate(decisions, start=1)
    ]

