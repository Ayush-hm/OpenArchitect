from operator import add
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

from openarchitect.core.schemas import ADR, ArchitectureDecision, ArchitectureGraph, DiagramSpec, ReviewFinding
from openarchitect.core.contracts.model_provider import ModelProvider
from openarchitect.core.schemas import ArchitectureReviewRequest, WorkflowResult
from openarchitect.modules.adr import generate_adrs
from openarchitect.modules.adr.validation import validate_adrs
from openarchitect.modules.diagram import generate_mermaid, plan_architecture_v2_with_llm
from openarchitect.modules.extraction.llm_service import extract_architecture_with_llm
from openarchitect.modules.ingestion import ingest_text
from openarchitect.modules.planning.lead_architect_service import consolidate_with_lead_architect_llm
from openarchitect.modules.review.coverage_service import critique_finding_coverage
from openarchitect.modules.review.frameworks import FrameworkProfile, get_framework_profile
from openarchitect.modules.review.llm_service import review_architecture_for_pillar_with_llm
from openarchitect.observability import traceable_step


class ArchitectureReviewState(TypedDict, total=False):
    document_text: str
    architecture_v1: ArchitectureGraph
    pillar_findings: Annotated[list[ReviewFinding], add]
    reviewed_pillars: Annotated[list[str], add]
    review_findings: list[ReviewFinding]
    findings: list[ReviewFinding]
    decisions: list[ArchitectureDecision]
    adrs: list[ADR]
    architecture_v2: ArchitectureGraph
    diagram: DiagramSpec


@traceable_step(name="OpenArchitect Architecture Review", run_type="chain")
async def run_architecture_review(
    request: ArchitectureReviewRequest,
    model_provider: ModelProvider,
) -> WorkflowResult:
    """Run the LangGraph LLM review workflow."""
    document_text = ingest_text(request.document_text)
    state = await _run_llm_review_graph(document_text, model_provider)
    architecture_v1 = state["architecture_v1"]
    findings = state["findings"]
    decisions = state["decisions"]
    adrs = state["adrs"]
    architecture_v2 = state["architecture_v2"]
    diagram = state["diagram"]

    return WorkflowResult(
        architecture_v1=architecture_v1,
        findings=findings,
        decisions=decisions,
        adrs=adrs,
        architecture_v2=architecture_v2,
        diagram=diagram,
    )


async def _run_llm_review_graph(
    document_text: str,
    model_provider: ModelProvider,
    framework: FrameworkProfile | None = None,
) -> ArchitectureReviewState:
    framework = framework or get_framework_profile()
    workflow = _build_llm_review_graph(model_provider, framework)
    return await workflow.ainvoke(
        {"document_text": document_text},
        config={
            "run_name": "OpenArchitect LangGraph Review",
            "tags": ["openarchitect", framework.id],
            "metadata": {
                "framework": framework.id,
                "pillar_count": len(framework.pillars),
                "document_chars": len(document_text),
            },
        },
    )


def _build_llm_review_graph(
    model_provider: ModelProvider,
    framework: FrameworkProfile | None = None,
):
    framework = framework or get_framework_profile()

    async def extract_node(state: ArchitectureReviewState) -> ArchitectureReviewState:
        architecture = await extract_architecture_with_llm(state["document_text"], model_provider)
        return {"architecture_v1": architecture}

    def make_pillar_node(pillar_id: str):
        pillar = next(item for item in framework.pillars if item.id == pillar_id)

        async def pillar_node(state: ArchitectureReviewState) -> ArchitectureReviewState:
            findings = await review_architecture_for_pillar_with_llm(
                state["architecture_v1"],
                model_provider,
                framework,
                pillar,
                langsmith_extra={
                    "name": pillar.reviewer_role,
                    "metadata": {
                        "framework": framework.id,
                        "pillar": pillar.id,
                    },
                },
            )
            return {
                "pillar_findings": findings,
                "reviewed_pillars": [pillar.id],
            }

        return pillar_node

    async def finding_coverage_node(state: ArchitectureReviewState) -> ArchitectureReviewState:
        covered_findings = await critique_finding_coverage(
            state["architecture_v1"],
            state.get("pillar_findings", []),
            model_provider,
            framework,
            state.get("reviewed_pillars", []),
        )
        return {"review_findings": covered_findings}

    async def lead_architect_node(state: ArchitectureReviewState) -> ArchitectureReviewState:
        lead_output = await consolidate_with_lead_architect_llm(
            state["architecture_v1"],
            state.get("review_findings", []),
            model_provider,
            framework,
        )
        return {
            "findings": lead_output.findings,
            "decisions": lead_output.decisions,
        }

    async def adr_node(state: ArchitectureReviewState) -> ArchitectureReviewState:
        adrs = generate_adrs(state.get("decisions", []))
        adrs, _ = validate_adrs(
            adrs,
            state.get("decisions", []),
            state.get("findings", []),
            state["architecture_v1"],
        )
        return {"adrs": adrs}

    async def output_node(state: ArchitectureReviewState) -> ArchitectureReviewState:
        architecture_v2 = await plan_architecture_v2_with_llm(
            state["architecture_v1"],
            state.get("decisions", []),
            state.get("adrs", []),
            model_provider,
        )
        diagram = generate_mermaid(architecture_v2)
        return {
            "architecture_v2": architecture_v2,
            "diagram": diagram,
        }

    graph = StateGraph(ArchitectureReviewState)
    graph.add_node("extract_architecture", extract_node)
    reviewer_node_names: list[str] = []
    for pillar in framework.pillars:
        node_name = f"{pillar.id}_reviewer"
        reviewer_node_names.append(node_name)
        graph.add_node(node_name, make_pillar_node(pillar.id))
    graph.add_node("finding_coverage_critic", finding_coverage_node)
    graph.add_node("lead_architect", lead_architect_node)
    graph.add_node("generate_adrs", adr_node)
    graph.add_node("build_outputs", output_node)

    graph.add_edge(START, "extract_architecture")
    for node_name in reviewer_node_names:
        graph.add_edge("extract_architecture", node_name)
    graph.add_edge(reviewer_node_names, "finding_coverage_critic")
    graph.add_edge("finding_coverage_critic", "lead_architect")
    graph.add_edge("lead_architect", "generate_adrs")
    graph.add_edge("generate_adrs", "build_outputs")
    graph.add_edge("build_outputs", END)
    return graph.compile()
