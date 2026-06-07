import pytest

from openarchitect.modules.ingestion import extract_text_from_upload


def test_extract_text_from_txt_upload() -> None:
    text = extract_text_from_upload(
        "architecture.txt",
        b"Frontend calls Backend API.",
    )

    assert text == "Frontend calls Backend API."


def test_rejects_unsupported_upload_type() -> None:
    with pytest.raises(ValueError, match="Unsupported file type"):
        extract_text_from_upload("architecture.docx", b"content")

