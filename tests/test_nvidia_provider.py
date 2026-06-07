from openarchitect.providers.nvidia_nim.provider import _coerce_structured_output
from openarchitect.modules.review.llm_service import ReviewFindingsOutput


def test_coerces_bare_list_into_single_list_schema_field() -> None:
    value = [{"id": "security-001"}]

    coerced = _coerce_structured_output(value, ReviewFindingsOutput)

    assert coerced == {"findings": value}

