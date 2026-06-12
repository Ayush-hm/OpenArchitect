from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

try:
    from langsmith import traceable as _langsmith_traceable
    from langsmith.run_helpers import get_current_run_tree
except ImportError:  # pragma: no cover - only used when LangSmith is not installed.
    _langsmith_traceable = None
    get_current_run_tree = None


def traceable_step(
    name: str,
    run_type: str = "chain",
    metadata: dict[str, Any] | None = None,
    tags: list[str] | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Create a LangSmith trace span with sanitized inputs and outputs."""
    if _langsmith_traceable is None:
        return lambda func: func

    return _langsmith_traceable(
        name=name,
        run_type=run_type,
        metadata=metadata,
        tags=tags,
        process_inputs=_summarize_inputs,
        process_outputs=_summarize_outputs,
    )


def record_llm_usage(
    *,
    provider: str,
    model: str,
    usage: dict[str, Any] | None,
) -> None:
    """Attach OpenAI-compatible token usage to the active LangSmith LLM span."""
    if get_current_run_tree is None or not usage:
        return

    usage_metadata = _extract_usage_metadata(usage)
    if not usage_metadata:
        return

    run_tree = get_current_run_tree()
    if run_tree is None:
        return

    run_tree.set(
        metadata={
            "ls_provider": provider,
            "ls_model_name": model,
        },
        usage_metadata=usage_metadata,
    )


def _extract_usage_metadata(usage: dict[str, Any]) -> dict[str, int]:
    input_tokens = _int_or_none(
        usage.get("prompt_tokens")
        or usage.get("input_tokens")
        or usage.get("promptTokens")
    )
    output_tokens = _int_or_none(
        usage.get("completion_tokens")
        or usage.get("output_tokens")
        or usage.get("completionTokens")
    )
    total_tokens = _int_or_none(usage.get("total_tokens") or usage.get("totalTokens"))

    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens

    metadata: dict[str, int] = {}
    if input_tokens is not None:
        metadata["input_tokens"] = input_tokens
    if output_tokens is not None:
        metadata["output_tokens"] = output_tokens
    if total_tokens is not None:
        metadata["total_tokens"] = total_tokens
    return metadata


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _summarize_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    return {key: _summarize_value(value) for key, value in inputs.items()}


def _summarize_outputs(outputs: Any) -> Any:
    return _summarize_value(outputs)


def _summarize_value(value: Any) -> Any:
    if value is None or isinstance(value, bool | int | float):
        return value

    if isinstance(value, str):
        return {
            "type": "str",
            "chars": len(value),
            "lines": value.count("\n") + 1 if value else 0,
        }

    if isinstance(value, type):
        return {"type": "type", "name": value.__name__}

    if isinstance(value, BaseModel):
        return _summarize_model(value)

    class_name = value.__class__.__name__
    if class_name == "FrameworkProfile":
        return {
            "type": class_name,
            "id": getattr(value, "id", None),
            "pillars": len(getattr(value, "pillars", [])),
        }
    if class_name == "PillarProfile":
        return {
            "type": class_name,
            "id": getattr(value, "id", None),
            "name": getattr(value, "name", None),
        }

    if isinstance(value, list | tuple | set):
        items = list(value)
        return {
            "type": type(value).__name__,
            "count": len(items),
            "sample": [_summarize_value(item) for item in items[:5]],
        }

    if isinstance(value, dict):
        return {
            "type": "dict",
            "keys": sorted(str(key) for key in value.keys())[:25],
            "size": len(value),
        }

    metadata = getattr(value, "metadata", None)
    if isinstance(metadata, dict):
        return {
            "type": value.__class__.__name__,
            "metadata": _sanitize_metadata(metadata),
        }

    return {"type": class_name}


def _summarize_model(value: BaseModel) -> dict[str, Any]:
    name = value.__class__.__name__
    if name == "ArchitectureGraph":
        nodes = getattr(value, "nodes", [])
        edges = getattr(value, "edges", [])
        constraints = getattr(value, "constraints", [])
        unknowns = getattr(value, "unknowns", [])
        return {
            "type": name,
            "nodes": len(nodes),
            "edges": len(edges),
            "constraints": len(constraints),
            "unknowns": len(unknowns),
        }

    if name == "WorkflowResult":
        return {
            "type": name,
            "findings": len(getattr(value, "findings", [])),
            "decisions": len(getattr(value, "decisions", [])),
            "adrs": len(getattr(value, "adrs", [])),
        }

    if name == "ReviewFinding":
        return {
            "type": name,
            "id": getattr(value, "id", None),
            "pillar": getattr(value, "pillar", None),
            "severity": str(getattr(value, "severity", "")),
            "requires_adr": getattr(value, "requires_adr", None),
        }

    if name == "ArchitectureDecision":
        return {
            "type": name,
            "id": getattr(value, "id", None),
            "linked_findings": len(getattr(value, "linked_finding_ids", [])),
            "impacted_components": len(getattr(value, "impacted_components", [])),
        }

    if name == "ADR":
        return {
            "type": name,
            "id": getattr(value, "id", None),
            "linked_findings": len(getattr(value, "linked_findings", [])),
            "impacted_components": len(getattr(value, "impacted_components", [])),
        }

    if name == "FrameworkProfile":
        return {
            "type": name,
            "id": getattr(value, "id", None),
            "pillars": len(getattr(value, "pillars", [])),
        }

    if name == "PillarProfile":
        return {
            "type": name,
            "id": getattr(value, "id", None),
            "name": getattr(value, "name", None),
        }

    return {"type": name}


def _sanitize_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in metadata.items():
        if "key" in key.lower() or "token" in key.lower() or "secret" in key.lower():
            sanitized[key] = bool(value)
            continue
        if key in {"provider", "model", "fallback_model"}:
            sanitized[key] = value
            continue
        sanitized[key] = _summarize_value(value)
    return sanitized
