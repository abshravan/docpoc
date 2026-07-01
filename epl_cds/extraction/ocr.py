"""OCR for uploaded scan-report files (Tesseract), with graceful degradation.

OCR is a *preprocessing* step: file -> text. The text then flows through the
same LLM fact-extraction, so the firewall is unchanged (the LLM still only
produces Facts; the deterministic engine still decides).

Tesseract is a system binary, not a pip package. Everything here imports lazily
and `default_ocr_fn()` returns None when OCR isn't available, so the build, the
tests, and manual fact entry never depend on it.
"""

from __future__ import annotations

import io
from typing import Optional

from epl_cds.contracts import OcrFn


class OCRUnavailable(RuntimeError):
    """Raised when OCR is requested but the required tooling isn't installed."""


def _image_to_text(data: bytes) -> str:
    import pytesseract  # lazy; requires the tesseract binary
    from PIL import Image

    with Image.open(io.BytesIO(data)) as img:
        return pytesseract.image_to_string(img)


def _pdf_to_text(data: bytes) -> str:
    # Prefer rendering pages (scanned PDFs); fall back to embedded text.
    try:
        from pdf2image import convert_from_bytes  # needs poppler
        import pytesseract

        pages = convert_from_bytes(data)
        return "\n\n".join(pytesseract.image_to_string(p) for p in pages)
    except Exception:
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(data))
            text = "\n\n".join((page.extract_text() or "") for page in reader.pages)
            if text.strip():
                return text
        except Exception:
            pass
        raise OCRUnavailable("PDF OCR requires pdf2image+poppler or a text PDF")


def tesseract_ocr(data: bytes, content_type: str) -> str:
    """OCR image or PDF bytes to text. Raises OCRUnavailable if tooling is missing."""
    ct = (content_type or "").lower()
    try:
        if "pdf" in ct:
            return _pdf_to_text(data)
        return _image_to_text(data)
    except OCRUnavailable:
        raise
    except ImportError as exc:
        raise OCRUnavailable(f"OCR dependencies missing: {exc}") from exc
    except Exception as exc:  # tesseract binary missing, unreadable file, etc.
        raise OCRUnavailable(f"OCR failed: {exc}") from exc


def ocr_available() -> bool:
    try:
        import pytesseract  # noqa: F401
        from PIL import Image  # noqa: F401
    except Exception:
        return False
    # Confirm the tesseract binary is actually reachable.
    try:
        import pytesseract

        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def default_ocr_fn() -> Optional[OcrFn]:
    """Return the Tesseract OCR function if available, else None."""
    return tesseract_ocr if ocr_available() else None
