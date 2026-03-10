import faiss
import numpy as np

class FaissHNSW:
    """
    FAISS HNSW index for ANN search.
    Uses inner product metric, which equals cosine similarity if vectors are normalized.
    """
    def __init__(self, dim: int, M: int = 32, ef_construction: int = 200, ef_search: int = 128):
        self.dim = dim
        self.index = faiss.IndexHNSWFlat(dim, M, faiss.METRIC_INNER_PRODUCT)
        self.index.hnsw.efConstruction = ef_construction
        self.index.hnsw.efSearch = ef_search

    def add(self, vectors: np.ndarray):
        self.index.add(vectors.astype("float32"))

    def search(self, query_vec: np.ndarray, top_k: int):
        """
        query_vec shape: (1, dim)
        Returns (scores, ids)
        """
        return self.index.search(query_vec.astype("float32"), top_k)

    def save(self, path: str):
        faiss.write_index(self.index, path)

    @staticmethod
    def load(path: str, ef_search: int = 128):
        idx = faiss.read_index(path)
        # set efSearch if HNSW
        try:
            idx.hnsw.efSearch = ef_search
        except Exception:
            pass
        obj = FaissHNSW(dim=1)
        obj.index = idx
        obj.dim = idx.d
        return obj
