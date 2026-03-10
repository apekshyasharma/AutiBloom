import re
from typing import List
from rag_system.ingestion.cleaners import clean_text
from rag_system.chunking.fixed import fixed_chunk

HEADING_WORDS = [
    "abstract", "introduction", "related work", "background",
    "method", "methods", "approach", "experiments", "results",
    "discussion", "conclusion", "references"
]

def split_semantically(text: str) -> List[str]:
    """
    Heuristic semantic splitting:
    - inserts strong breaks around common research paper section headings
    - then splits into paragraph-like blocks
    """
    t = text.replace("\r", "\n")

    # Insert breaks around headings (heuristic)
    for h in HEADING_WORDS:
        # match heading word as a standalone line-ish token
        t = re.sub(rf"\s+({re.escape(h)})\s+", r"\n\n\1\n\n", t, flags=re.IGNORECASE)

    # Split on blank lines / paragraph breaks
    parts = re.split(r"\n\s*\n+", t)
    parts = [clean_text(p) for p in parts if clean_text(p)]
    return parts

def semantic_chunk(text: str, max_chunk_size: int, overlap: int, min_len: int = 200) -> List[str]:
    """
    Semantic chunking with overlap support:
    - split into semantic blocks (paragraphs/sections)
    - merge blocks until max_chunk_size
    - if any merged block exceeds max size, fall back to fixed chunking with overlap
    """
    blocks = split_semantically(text)

    merged = []
    buf = ""

    def flush():
        nonlocal buf
        if buf.strip():
            merged.append(buf.strip())
        buf = ""

    for b in blocks:
        # Merge blocks until size cap
        if buf and len(buf) + 1 + len(b) > max_chunk_size:
            flush()
        buf = (buf + " " + b).strip() if buf else b

    flush()

    # Ensure max size by fallback splitting
    final_chunks: List[str] = []
    for m in merged:
        if len(m) <= max_chunk_size:
            final_chunks.append(m)
        else:
            final_chunks.extend(fixed_chunk(m, max_chunk_size, overlap, min_len=min_len))

    return [c for c in final_chunks if len(c) >= min_len]
