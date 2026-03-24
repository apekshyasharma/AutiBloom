from dataclasses import dataclass
from pathlib import Path
import yaml

@dataclass(frozen=True)
class Settings:
    # Paths
    project_root: Path
    artifacts_dir: Path
    pdf_dir: Path
    prompts_dir: Path

    # Chunking
    chunk_size: int
    overlap: int
    fixed_enabled: bool
    semantic_enabled: bool

    # Embeddings
    embed_model: str
    normalize_embeddings: bool

    # FAISS HNSW
    hnsw_M: int
    ef_construction: int
    ef_search: int

    # Retrieval
    bm25_k: int
    dense_k: int
    final_k: int
    rrf_k: int
    max_per_doc: int
    chunking_mode_default: str  # fixed | semantic | both | auto

    # LLM
    llm_model: str
    temperature: float
    max_output_tokens: int

def load_settings(config_path: str = "configs/default.yaml") -> Settings:
    """
    Loads configs/default.yaml and resolves all paths relative to the project root.
    Assumes you run from the 'rag/' directory.
    """
    root = Path(__file__).resolve().parents[2]  # rag/src/rag_system/config.py -> rag/
    cfg_file = root / config_path

    with open(cfg_file, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    paths = cfg.get("paths", {})
    chunking = cfg.get("chunking", {})
    embedding = cfg.get("embedding", {})
    faiss_cfg = cfg.get("faiss", {})
    retrieval = cfg.get("retrieval", {})
    llm = cfg.get("llm", {})

    return Settings(
        project_root=root,
        artifacts_dir=root / paths.get("artifacts_dir", "artifacts"),
        pdf_dir=root / paths.get("pdf_dir", "data/raw_pdfs"),
        prompts_dir=root / paths.get("prompts_dir", "configs/prompts"),

        chunk_size=int(chunking.get("chunk_size", 1200)),
        overlap=int(chunking.get("overlap", 200)),
        fixed_enabled=bool(chunking.get("fixed_enabled", True)),
        semantic_enabled=bool(chunking.get("semantic_enabled", True)),

        embed_model=str(embedding.get("model_name", "sentence-transformers/all-MiniLM-L6-v2")),
        normalize_embeddings=bool(embedding.get("normalize", True)),

        hnsw_M=int(faiss_cfg.get("M", 32)),
        ef_construction=int(faiss_cfg.get("ef_construction", 200)),
        ef_search=int(faiss_cfg.get("ef_search", 128)),

        bm25_k=int(retrieval.get("bm25_k", 200)),
        dense_k=int(retrieval.get("dense_k", 50)),
        final_k=int(retrieval.get("final_k", 8)),
        rrf_k=int(retrieval.get("rrf_k", 60)),
        max_per_doc=int(retrieval.get("max_per_doc", 2)),
        chunking_mode_default=str(retrieval.get("chunking_mode_default", "semantic")),

        llm_model=str(llm.get("model", "gemini-2.5-flash")),
        temperature=float(llm.get("temperature", 0.2)),
        max_output_tokens=int(llm.get("max_output_tokens", 800)),
    )
