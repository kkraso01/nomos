"""Document text extraction for matter ingestion (deterministic, no ML)."""
import os


def extract_text_from_bytes(data: bytes, filename: str | None = None) -> str:
    """Extract UTF-8 text from an uploaded matter document.

    Supports plain text and PDF (via PyMuPDF). Returns '' when no text is
    recoverable for other formats; those remain stored raw for later OCR/parsing.
    """
    name = (filename or "").lower()

    if name.endswith(".pdf"):
        return _extract_pdf(data)

    if name.endswith(".txt") or name.endswith(".md") or name.endswith(".csv"):
        return data.decode("utf-8", "replace")

    # Fallback: try to sniff as text by content.
    try:
        text = data.decode("utf-8")
        # reject binary-looking content
        if "\x00" in text:
            return ""
        return text
    except UnicodeDecodeError:
        return ""


def _extract_pdf(data: bytes) -> str:
    try:
        import pymupdf  # PyMuPDF >= 1.24 CLI-compatible
    except Exception:  # pragma: no cover
        try:
            import fitz as pymupdf
        except Exception:  # noqa: BLE001
            return ""

    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception:  # pragma: no cover
        return ""
    parts = []
    for page in doc:
        parts.append(page.get_text("text"))
    doc.close()
    text = "\n".join(parts)
    return text.strip()