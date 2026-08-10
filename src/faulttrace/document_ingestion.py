"""Extract local text from uploaded knowledge-base documents."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from pypdf import PdfReader


SUPPORTED_DOCUMENT_TYPES = {".txt", ".md", ".pdf"}


def safe_source_name(filename: str) -> str:
    """Normalize an uploaded filename and keep it in the custom namespace."""

    name = Path(filename).name.strip().replace("\\", "_").replace("/", "_")
    if not name:
        raise ValueError("Document filename is empty.")
    return f"custom/{name}"


def extract_document_text(filename: str, content: bytes) -> str:
    """Extract text from an in-memory TXT, Markdown or text-based PDF file."""

    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_DOCUMENT_TYPES:
        raise ValueError(f"Unsupported document type: {suffix or 'none'}")
    if len(content) > 10 * 1024 * 1024:
        raise ValueError("Document exceeds the 10 MB local indexing limit.")

    if suffix in {".txt", ".md"}:
        text = content.decode("utf-8-sig", errors="replace")
    else:
        reader = PdfReader(BytesIO(content))
        text = "\n\n".join(page.extract_text() or "" for page in reader.pages)

    text = text.strip()
    if not text:
        raise ValueError("No extractable text was found in the document.")
    return text

