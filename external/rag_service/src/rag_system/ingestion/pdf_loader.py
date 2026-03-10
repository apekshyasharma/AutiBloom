"""Extract text from PDF using PyMuPDF."""
from pathlib import Path
import fitz  # PyMuPDF

def extract_text_from_pdf(pdf_path: Path) -> str:
    """
    Extract text from a PDF using PyMuPDF.
    Returns concatenated text from all pages.
    """
    doc = fitz.open(str(pdf_path))
    parts = []
    for page in doc:
        parts.append(page.get_text("text"))
    return "\n".join(parts)
