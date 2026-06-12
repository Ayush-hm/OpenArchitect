from openarchitect.observability.langsmith import _extract_usage_metadata


def test_extracts_openai_compatible_usage_metadata() -> None:
    usage = {
        "prompt_tokens": 123,
        "completion_tokens": 45,
        "total_tokens": 168,
    }

    assert _extract_usage_metadata(usage) == {
        "input_tokens": 123,
        "output_tokens": 45,
        "total_tokens": 168,
    }


def test_extracts_total_tokens_when_not_provided() -> None:
    usage = {
        "input_tokens": "10",
        "output_tokens": "7",
    }

    assert _extract_usage_metadata(usage) == {
        "input_tokens": 10,
        "output_tokens": 7,
        "total_tokens": 17,
    }
