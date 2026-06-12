import asyncio
from typing import Any

from pydantic import BaseModel

from openarchitect.core.contracts.model_provider import ModelProvider
from openarchitect.modules.extraction.llm_service import extract_architecture_with_llm


TAIL_MARKER = "TAIL_COMPONENT_BEYOND_OLD_TRUNCATION_LIMIT"


class FullDocumentPromptProvider(ModelProvider):
    def __init__(self) -> None:
        self.seen_text_prompt = False
        self.seen_structured_prompt = False

    @property
    def metadata(self) -> dict[str, Any]:
        return {"provider": "fake"}

    async def generate_text(self, prompt: str) -> str:
        assert TAIL_MARKER in prompt
        self.seen_text_prompt = True
        return """
{
  "architecture": {
    "nodes": [],
    "edges": [],
    "constraints": [],
    "unknowns": []
  }
}
"""

    async def generate_structured(
        self,
        prompt: str,
        schema: type[BaseModel],
    ) -> BaseModel:
        assert schema.__name__ == "GraphCriticPatchOutput"
        assert TAIL_MARKER in prompt
        self.seen_structured_prompt = True
        return schema()


def test_extraction_and_graph_critic_receive_entire_document() -> None:
    provider = FullDocumentPromptProvider()
    document_text = "A" * 13_000 + TAIL_MARKER

    asyncio.run(extract_architecture_with_llm(document_text, provider))

    assert provider.seen_text_prompt is True
    assert provider.seen_structured_prompt is True
