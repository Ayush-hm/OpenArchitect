from openarchitect.core.schemas import ArchitectureReviewRequest, WorkflowResult
from openarchitect.providers import create_model_provider
from openarchitect.runtime.langgraph import run_architecture_review


async def run_review_workflow(request: ArchitectureReviewRequest) -> WorkflowResult:
    provider = create_model_provider()
    return await run_architecture_review(request, provider)
