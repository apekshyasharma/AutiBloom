from typing import List
from rag_system.ingestion.cleaners import clean_text

def fixed_chunk(text: str, chunk_size: int, overlap: int, min_len: int = 200) -> List[str]:
    """
    Fixed-size chunking with overlap.
    step = chunk_size - overlap
    """
    text = clean_text(text)
    out = []
    step = max(1, chunk_size - overlap)

    for start in range(0, len(text), step):
        end = min(len(text), start + chunk_size)
        chunk = text[start:end].strip()
        if len(chunk) >= min_len:
            out.append(chunk)
        if end == len(text):
            break
    return out
