import os

from dotenv import load_dotenv

from openarchitect.core.contracts.model_provider import ModelProvider
from openarchitect.providers.gemini import GeminiProvider
from openarchitect.providers.nvidia_nim import NvidiaNimProvider

load_dotenv()


def create_model_provider(provider_name: str | None = None) -> ModelProvider:
    name = (provider_name or os.getenv("OPENARCHITECT_MODEL_PROVIDER") or "gemini").strip().lower()

    if name in {"gemini", "google", "google_ai_studio"}:
        return GeminiProvider()
    if name in {"nvidia_nim", "nvidia", "nim", "nemotron"}:
        return NvidiaNimProvider()

    raise RuntimeError(
        "Unsupported model provider "
        f"'{name}'. Supported providers: gemini, nvidia_nim."
    )
