import json
import re
from typing import Any

from pydantic import BaseModel


def extract_json_object(text: str) -> Any:
    stripped = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", stripped, re.DOTALL | re.IGNORECASE)
    if fenced:
        stripped = fenced.group(1).strip()

    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start >= 0 and end > start:
            return json.loads(stripped[start : end + 1])
        raise


def compact_schema(schema: type[BaseModel]) -> str:
    return json.dumps(schema.model_json_schema(), separators=(",", ":"))


def coerce_structured_output(value: Any, schema: type[BaseModel]) -> Any:
    if not isinstance(value, list):
        return value

    list_fields = [
        name
        for name, field in schema.model_fields.items()
        if getattr(field.annotation, "__origin__", None) is list
    ]
    if len(list_fields) == 1:
        return {list_fields[0]: value}
    return value
