from io import BytesIO

from pypdf import PdfReader


def ingest_text(document_text: str) -> str:
    """Normalize raw architecture text for downstream extraction."""
    return " ".join(document_text.split())


def extract_text_from_upload(filename: str, content: bytes) -> str:
    """Extract text from supported SAD upload formats."""
    lowered = filename.lower()
    if lowered.endswith(".pdf"):
        return _extract_pdf_text(content)
    if lowered.endswith(".txt") or lowered.endswith(".md"):
        return content.decode("utf-8", errors="replace")
    raise ValueError("Unsupported file type. Upload a .pdf, .txt, or .md file.")


def _extract_pdf_text(content: bytes) -> str:
    reader = PdfReader(BytesIO(content))
    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n".join(page.strip() for page in pages if page.strip())
    if not text:
        raise ValueError("No extractable text found in PDF.")
    return text
