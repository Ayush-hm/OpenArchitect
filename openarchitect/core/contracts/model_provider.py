from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class ModelProvider(ABC):
    """Model provider boundary used by modules and runtime adapters."""

    @abstractmethod
    async def generate_text(self, prompt: str) -> str:
        """Generate free-form text."""

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        schema: type[BaseModel],
    ) -> BaseModel:
        """Generate output matching a Pydantic schema."""

    @property
    @abstractmethod
    def metadata(self) -> dict[str, Any]:
        """Provider metadata useful for traces and diagnostics."""

