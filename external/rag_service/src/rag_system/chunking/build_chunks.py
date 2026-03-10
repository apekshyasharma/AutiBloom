from pathlib import Path
from typing import Dict, List
from rag_system.chunking.fixed import fixed_chunk
from rag_system.chunking.semantic import semantic_chunk

def build_chunks_for_doc(
    source_path: Path,
    text: str,
    chunk_size: int,
    overlap: int,
    fixed_enabled: bool,
    semantic_enabled: bool
) -> Dict[str, List[Dict]]:
    """
    Returns TWO separate chunk lists keyed by strategy:
      {
        "fixed":   [chunk_dicts...],
        "semantic":[chunk_dicts...]
      }

    Each chunk_dict includes metadata needed for citations and debugging.
    """
    base = source_path.name

    out = {"fixed": [], "semantic": []}

    if fixed_enabled:
        parts = fixed_chunk(text, chunk_size, overlap)
        for i, p in enumerate(parts):
            out["fixed"].append({
                "chunk_id": f"{base}::fixed::chunk{i}",
                "source": str(source_path),
                "strategy": "fixed_overlap",
                "text": p
            })

    if semantic_enabled:
        parts = semantic_chunk(text, chunk_size, overlap)
        for i, p in enumerate(parts):
            out["semantic"].append({
                "chunk_id": f"{base}::semantic::chunk{i}",
                "source": str(source_path),
                "strategy": "semantic_overlap",
                "text": p
            })

    return out
