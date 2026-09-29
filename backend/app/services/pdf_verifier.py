"""PDF document verification (Phase 19.5: basic + content-integrity checks).

The basic checks (exists, page count, text layer, candidate name) are
necessary but insufficient - a corrupted render passes them. The integrity
layer verifies the extracted TEXT against the structured expectations:

- expected major sections remain present
- accepted tailoring changes appear; rejected/blocked ones do not
- obvious concatenation artifacts are detected (glued headers, missing
  spaces after sentence boundaries)
- the document retains a sane share of the base resume content
"""

import re
from pathlib import Path

import structlog
from pydantic import BaseModel

logger = structlog.get_logger(__name__)

# A lowercase letter directly followed by 3+ uppercase letters is a glued
# ALL-CAPS header ("...InstitutesPROJECTS").
_GLUED_HEADER_RE = re.compile(r"[a-z][A-Z]{3,}")
# A lowercase letter + period + capitalized word with NO space is a glued
# sentence boundary ("...lifecycle.Technology").
_GLUED_SENTENCE_RE = re.compile(r"[a-z]\.[A-Z][a-z]+")


class PDFVerificationResult(BaseModel):
    is_valid: bool
    reason: str | None = None
    page_count: int = 0
    text_length: int = 0
    missing_sections: list[str] = []
    missing_texts: list[str] = []
    forbidden_texts_found: list[str] = []
    concatenation_issues: list[str] = []


def check_document_integrity(
    text: str,
    *,
    expected_sections: list[str] | None = None,
    required_texts: list[str] | None = None,
    forbidden_texts: list[str] | None = None,
    base_text: str | None = None,
    min_retention: float = 0.5,
) -> PDFVerificationResult:
    """Deterministic content-integrity checks over extracted document text."""
    problems: list[str] = []
    lower = text.lower()

    missing_sections = [s for s in (expected_sections or []) if s.lower() not in lower]
    if missing_sections:
        problems.append(f"missing sections: {', '.join(missing_sections)}")

    missing_texts = [
        t for t in (required_texts or []) if t and t.strip()[:60].lower() not in lower
    ]
    if missing_texts:
        problems.append("accepted changes missing from document")

    forbidden_texts_found = [
        t for t in (forbidden_texts or []) if t and t.strip()[:60].lower() in lower
    ]
    if forbidden_texts_found:
        problems.append("rejected/blocked changes present in document")

    concatenation_issues = [
        *[_m.group() for _m in _GLUED_HEADER_RE.finditer(text)],
        *[_m.group() for _m in _GLUED_SENTENCE_RE.finditer(text)],
    ]
    if len(concatenation_issues) > 3:
        problems.append(f"concatenation artifacts detected: {concatenation_issues[:5]}")

    if base_text:
        # Content retention: the final document must not lose large portions
        # of the base resume (compare alphanumeric content sizes).
        def _weight(s: str) -> int:
            return len(re.sub(r"[^A-Za-z0-9]", "", s))

        ratio = _weight(text) / max(_weight(base_text), 1)
        if ratio < min_retention:
            problems.append(f"content retention too low: {ratio:.0%} of base resume")

    return PDFVerificationResult(
        is_valid=not problems,
        reason="; ".join(problems) or None,
        missing_sections=missing_sections,
        missing_texts=missing_texts,
        forbidden_texts_found=forbidden_texts_found,
        concatenation_issues=concatenation_issues[:10],
    )


def verify_pdf_document(
    pdf_path: str,
    expected_name: str | None = None,
    *,
    expected_sections: list[str] | None = None,
    required_texts: list[str] | None = None,
    forbidden_texts: list[str] | None = None,
    base_text: str | None = None,
    min_retention: float = 0.5,
) -> PDFVerificationResult:
    """Verify a generated PDF for basic AND content-integrity correctness."""
    path = Path(pdf_path)

    if not path.exists():
        return PDFVerificationResult(is_valid=False, reason="File does not exist")
    if path.stat().st_size == 0:
        return PDFVerificationResult(is_valid=False, reason="File is empty")

    try:
        from PyPDF2 import PdfReader

        reader = PdfReader(str(path))

        num_pages = len(reader.pages)
        if num_pages == 0:
            return PDFVerificationResult(is_valid=False, reason="PDF has 0 pages")
        if num_pages > 20:
            return PDFVerificationResult(
                is_valid=False, reason="PDF page count exceeds sane limits (>20)"
            )

        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

        if len(text.strip()) < 50:
            return PDFVerificationResult(
                is_valid=False, reason="Text layer missing or extremely sparse"
            )

        if expected_name and expected_name.lower() not in text.lower():
            return PDFVerificationResult(
                is_valid=False,
                reason=f"Expected name '{expected_name}' not found in PDF",
            )

        integrity = check_document_integrity(
            text,
            expected_sections=expected_sections,
            required_texts=required_texts,
            forbidden_texts=forbidden_texts,
            base_text=base_text,
            min_retention=min_retention,
        )
        result = PDFVerificationResult(
            is_valid=integrity.is_valid,
            reason=integrity.reason,
            page_count=num_pages,
            text_length=len(text),
            missing_sections=integrity.missing_sections,
            missing_texts=integrity.missing_texts,
            forbidden_texts_found=integrity.forbidden_texts_found,
            concatenation_issues=integrity.concatenation_issues,
        )
        if not result.is_valid:
            logger.warning("pdf_integrity_failed", reason=result.reason)
        return result

    except ImportError:
        logger.warning("PyPDF2 not installed, skipping advanced PDF validation.")
        return PDFVerificationResult(
            is_valid=True, reason="PyPDF2 not installed, fallback to exist-only check"
        )
    except Exception as e:
        logger.error("PDF verification failed", error=str(e))
        return PDFVerificationResult(is_valid=False, reason=f"PDF parsing failed: {e}")
