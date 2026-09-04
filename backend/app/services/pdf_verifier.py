import structlog
from pathlib import Path
from pydantic import BaseModel

logger = structlog.get_logger(__name__)

class PDFVerificationResult(BaseModel):
    is_valid: bool
    reason: str | None = None
    page_count: int = 0
    text_length: int = 0

def verify_pdf_document(pdf_path: str, expected_name: str | None = None) -> PDFVerificationResult:
    """
    Verify a generated PDF document for basic correctness.
    """
    path = Path(pdf_path)
    
    # 1. Exists and non-empty
    if not path.exists():
        return PDFVerificationResult(is_valid=False, reason="File does not exist")
    if path.stat().st_size == 0:
        return PDFVerificationResult(is_valid=False, reason="File is empty")
        
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(str(path))
        
        # 3. PDF opens and has sane page count
        num_pages = len(reader.pages)
        if num_pages == 0:
            return PDFVerificationResult(is_valid=False, reason="PDF has 0 pages")
        if num_pages > 20:
            return PDFVerificationResult(is_valid=False, reason="PDF page count exceeds sane limits (>20)")
            
        # 5. Text layer exists
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
                
        if len(text.strip()) < 50:
            return PDFVerificationResult(is_valid=False, reason="Text layer missing or extremely sparse")
            
        # 6. Candidate name exists (basic text match)
        if expected_name and expected_name.lower() not in text.lower():
            return PDFVerificationResult(is_valid=False, reason=f"Expected name '{expected_name}' not found in PDF")
            
        return PDFVerificationResult(
            is_valid=True, 
            page_count=num_pages,
            text_length=len(text)
        )
    except ImportError:
        logger.warning("PyPDF2 not installed, skipping advanced PDF validation.")
        return PDFVerificationResult(is_valid=True, reason="PyPDF2 not installed, fallback to exist-only check")
    except Exception as e:
        logger.error("PDF verification failed", error=str(e))
        return PDFVerificationResult(is_valid=False, reason=f"PDF parsing failed: {e}")

