from uuid import uuid4

from openarchitect.core.schemas import WorkflowResult


class InMemoryWorkflowStore:
    def __init__(self) -> None:
        self._runs: dict[str, WorkflowResult] = {}

    def save(self, result: WorkflowResult) -> str:
        run_id = str(uuid4())
        self._runs[run_id] = result
        return run_id

    def get(self, run_id: str) -> WorkflowResult | None:
        return self._runs.get(run_id)

