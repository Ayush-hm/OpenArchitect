import os
from typing import Any

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

from openarchitect.core.contracts.model_provider import ModelProvider
from openarchitect.providers.structured_output import (
    coerce_structured_output,
    compact_schema,
    extract_json_object,
)
from openarchitect.observability import record_llm_usage, traceable_step

load_dotenv()


class GeminiProvider(ModelProvider):
    """Google AI Studio Gemini provider through the OpenAI-compatible API."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.base_url = (
            base_url
            or os.getenv("GEMINI_BASE_URL")
            or "https://generativelanguage.googleapis.com/v1beta/openai"
        ).rstrip("/")
        self.model = model or os.getenv("GEMINI_MODEL") or "gemini-2.5-flash"
        self.fallback_model = os.getenv("GEMINI_FALLBACK_MODEL", "").strip()
        self.primary_timeout_seconds = float(os.getenv("GEMINI_PRIMARY_TIMEOUT_SECONDS", "60"))
        self.timeout_seconds = float(os.getenv("GEMINI_TIMEOUT_SECONDS", "180"))
        self.max_tokens = int(os.getenv("GEMINI_MAX_TOKENS", "4096"))
        self.force_json_response = os.getenv("GEMINI_FORCE_JSON_RESPONSE", "").lower() == "true"
        self.reasoning_effort = os.getenv("GEMINI_REASONING_EFFORT", "").strip()

    @property
    def metadata(self) -> dict[str, Any]:
        return {
            "provider": "gemini",
            "model": self.model,
            "fallback_model": self.fallback_model or None,
            "base_url_configured": bool(self.base_url),
            "api_key_configured": bool(self.api_key),
            "primary_timeout_seconds": self.primary_timeout_seconds,
            "timeout_seconds": self.timeout_seconds,
            "max_tokens": self.max_tokens,
            "force_json_response": self.force_json_response,
            "reasoning_effort": self.reasoning_effort or None,
        }

    @traceable_step(
        name="Gemini Generate Text",
        run_type="llm",
        metadata={"provider": "gemini"},
    )
    async def generate_text(self, prompt: str) -> str:
        if not self.api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is required for LLM mode. "
                "Set OPENARCHITECT_MODEL_PROVIDER=nvidia_nim to use NVIDIA NIM instead."
            )

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are OpenArchitect. Return valid JSON only when asked for structured output.",
                },
                {"role": "user", "content": prompt},
            ],
            "max_tokens": self.max_tokens,
            "temperature": 0.0,
            "stream": False,
        }
        if self.force_json_response:
            payload["response_format"] = {"type": "json_object"}
        if self.reasoning_effort:
            payload["reasoning_effort"] = self.reasoning_effort

        try:
            return await self._chat_completion(
                payload,
                model=self.model,
                timeout_seconds=self.primary_timeout_seconds,
            )
        except httpx.ReadTimeout as exc:
            if not self.fallback_model or self.fallback_model == self.model:
                raise RuntimeError(
                    f"Gemini request timed out after {self.primary_timeout_seconds:.0f}s "
                    f"for model {self.model}. Try a faster model or set GEMINI_FALLBACK_MODEL."
                ) from exc
            return await self._chat_completion(
                payload,
                model=self.fallback_model,
                timeout_seconds=self.timeout_seconds,
            )

    async def _chat_completion(
        self,
        payload: dict[str, Any],
        model: str,
        timeout_seconds: float,
    ) -> str:
        payload = {**payload, "model": model}
        timeout = httpx.Timeout(
            timeout=timeout_seconds,
            connect=20.0,
            read=timeout_seconds,
            write=20.0,
            pool=20.0,
        )
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Accept": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                record_llm_usage(
                    provider="gemini",
                    model=model,
                    usage=data.get("usage"),
                )
                return data["choices"][0]["message"]["content"]
        except httpx.ReadTimeout as exc:
            raise exc
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"Gemini request failed with HTTP {exc.response.status_code}: "
                f"{exc.response.text[:500]}"
            ) from exc

    @traceable_step(
        name="Gemini Generate Structured",
        run_type="chain",
        metadata={"provider": "gemini"},
    )
    async def generate_structured(
        self,
        prompt: str,
        schema: type[BaseModel],
    ) -> BaseModel:
        text = await self.generate_text(
            f"{prompt}\n\n"
            "Return only a JSON instance that validates against the schema below. "
            "Do not return the schema itself. Do not include keys like $defs, "
            "properties, title, or type unless the output object genuinely requires them. "
            "Do not include Markdown fences or explanatory prose.\n\n"
            f"JSON Schema:\n{compact_schema(schema)}"
        )
        try:
            return schema.model_validate(coerce_structured_output(extract_json_object(text), schema))
        except (ValueError, ValidationError) as exc:
            repaired = await self.generate_text(
                "Convert the previous model output into a valid JSON instance for the schema. "
                "Return only valid JSON. Do not include Markdown or explanation.\n\n"
                f"Previous output:\n{text[:6000]}\n\n"
                f"JSON Schema:\n{compact_schema(schema)}"
            )
            try:
                return schema.model_validate(
                    coerce_structured_output(extract_json_object(repaired), schema)
                )
            except (ValueError, ValidationError) as repair_exc:
                raise RuntimeError(
                    "Gemini returned invalid structured JSON after repair retry: "
                    f"{repair_exc}"
                ) from exc
