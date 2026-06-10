import pytest

from openarchitect.providers.factory import create_model_provider
from openarchitect.providers.gemini import GeminiProvider
from openarchitect.providers.nvidia_nim import NvidiaNimProvider


def test_default_provider_is_gemini(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENARCHITECT_MODEL_PROVIDER", raising=False)

    provider = create_model_provider()

    assert isinstance(provider, GeminiProvider)


def test_can_select_nvidia_nim_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENARCHITECT_MODEL_PROVIDER", "nvidia_nim")

    provider = create_model_provider()

    assert isinstance(provider, NvidiaNimProvider)


def test_unknown_provider_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENARCHITECT_MODEL_PROVIDER", "unknown")

    with pytest.raises(RuntimeError, match="Unsupported model provider"):
        create_model_provider()
