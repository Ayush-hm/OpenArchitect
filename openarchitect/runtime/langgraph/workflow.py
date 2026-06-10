import os
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from openarchitect.core.schemas import ADR, ArchitectureDecision, ArchitectureGraph, DiagramSpec, ReviewFinding
from openarchitect.core.contracts.model_provider import ModelProvider
from openarchitect.core.schemas import ArchitectureReviewRequest, WorkflowResult
from openarchitect.modules.adr import generate_adrs
from openarchitect.modules.adr.validation import validate_adrs
from openarchitect.modules.diagram import build_architecture_v2, generate_mermaid, plan_architecture_v2_with_llm
from openarchitect.modules.extraction import extract_architecture
from openarchitect.modules.extraction.llm_service import extract_architecture_with_llm
from openarchitect.modules.ingestion import ingest_text
from openarchitect.modules.planning import plan_decisions
from openarchitect.modules.planning.lead_architect_service import consolidate_with_lead_architect_llm
from openarchitect.modules.review import review_architecture
from openarchitect.modules.review.coverage_service import critique_finding_coverage
from openarchitect.modules.review.llm_service import review_architecture_as_specialist_with_llm


class ArchitectureReviewState(TypedDict, total=False):
    document_text: str
    architecture_v1: ArchitectureGraph
    scalability_findings: list[ReviewFinding]
    reliability_findings: list[ReviewFinding]
    security_findings: list[ReviewFinding]
    finops_findings: list[ReviewFinding]
    review_findings: list[ReviewFinding]
    findings: list[ReviewFinding]
    decisions: list[ArchitectureDecision]
    adrs: list[ADR]
    architecture_v2: ArchitectureGraph
    diagram: DiagramSpec


async def run_architecture_review(
    request: ArchitectureReviewRequest,
    model_provider: ModelProvider,
) -> WorkflowResult:
    """Run the LangGraph runtime workflow.

    The current implementation keeps the node logic deterministic for the first
    working MVP path. The LangGraph adapter boundary is preserved so the same
    steps can be converted into a compiled StateGraph without changing modules.
    """
    document_text = ingest_text(request.document_text)
    allow_rule_fallback = os.getenv("OPENARCHITECT_ALLOW_RULE_FALLBACK") == "1"

    try:
        state = await _run_llm_review_graph(document_text, model_provider)
        architecture_v1 = state["architecture_v1"]
        findings = state["findings"]
        decisions = state["decisions"]
        adrs = state["adrs"]
        architecture_v2 = state["architecture_v2"]
        diagram = state["diagram"]
    except Exception:
        if not allow_rule_fallback:
            raise
        architecture_v1 = extract_architecture(document_text)
        findings = review_architecture(architecture_v1)
        decisions = plan_decisions(findings)
        adrs = generate_adrs(decisions)
        architecture_v2 = build_architecture_v2(architecture_v1, decisions)
        diagram = generate_mermaid(architecture_v2)

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
) -> ArchitectureReviewState:
    workflow = _build_llm_review_graph(model_provider)
    return await workflow.ainvoke({"document_text": document_text})


def _build_llm_review_graph(model_provider: ModelProvider):
    async def extract_node(state: ArchitectureReviewState) -> ArchitectureReviewState:
        architecture = await extract_architecture_with_llm(state["document_text"], model_provider)
        return {"architecture_v1": architecture}

    async def scalability_node(state: ArchitectureReviewState) -> ArchitectureReviewState:
        findings = await review_architecture_as_specialist_with_llm(
            state["architecture_v1"],
            model_provider,
            "Scalability Architect",
        )
        return {"scalability_findings": findings}

    async def reliability_node(state: ArchitectureReviewState) -> ArchitectureReviewState:
        findings = await review_architecture_as_specialist_with_llm(
            state["architecture_v1"],
            model_provider,
            "Reliability Architect",
        )
        return {"reliability_findings": findings}

    async def security_node(state: ArchitectureReviewState) -> ArchitectureReviewState:
        findings = await review_architecture_as_specialist_with_llm(
            state["architecture_v1"],
            model_provider,
            "Security Architect",
        )
        return {"security_findings": findings}

    async def finops_node(state: ArchitectureReviewState) -> ArchitectureReviewState:
        findings = await review_architecture_as_specialist_with_llm(
            state["architecture_v1"],
            model_provider,
            "FinOps Architect",
        )
        return {"finops_findings": findings}

    async def finding_coverage_node(state: ArchitectureReviewState) -> ArchitectureReviewState:
        specialist_findings = [
            *state.get("scalability_findings", []),
            *state.get("reliability_findings", []),
            *state.get("security_findings", []),
            *state.get("finops_findings", []),
        ]
        covered_findings = await critique_finding_coverage(
            state["architecture_v1"],
            specialist_findings,
            model_provider,
        )
        return {"review_findings": covered_findings}

    async def lead_architect_node(state: ArchitectureReviewState) -> ArchitectureReviewState:
        lead_output = await consolidate_with_lead_architect_llm(
            state["architecture_v1"],
            state.get("review_findings", []),
            model_provider,
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
    graph.add_node("scalability_reviewer", scalability_node)
    graph.add_node("reliability_reviewer", reliability_node)
    graph.add_node("security_reviewer", security_node)
    graph.add_node("finops_reviewer", finops_node)
    graph.add_node("finding_coverage_critic", finding_coverage_node)
    graph.add_node("lead_architect", lead_architect_node)
    graph.add_node("generate_adrs", adr_node)
    graph.add_node("build_outputs", output_node)

    graph.add_edge(START, "extract_architecture")
    graph.add_edge("extract_architecture", "scalability_reviewer")
    graph.add_edge("extract_architecture", "reliability_reviewer")
    graph.add_edge("extract_architecture", "security_reviewer")
    graph.add_edge("extract_architecture", "finops_reviewer")
    graph.add_edge(
        [
            "scalability_reviewer",
            "reliability_reviewer",
            "security_reviewer",
            "finops_reviewer",
        ],
        "finding_coverage_critic",
    )
    graph.add_edge("finding_coverage_critic", "lead_architect")
    graph.add_edge("lead_architect", "generate_adrs")
    graph.add_edge("generate_adrs", "build_outputs")
    graph.add_edge("build_outputs", END)
    return graph.compile()
