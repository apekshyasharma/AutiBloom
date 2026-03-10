from sentence_transformers import SentenceTransformer
import numpy as np
from typing import List

class DenseEmbedder:
    """
    Wraps SentenceTransformers to produce dense vectors.
    If normalize=True, vectors are unit length => cosine similarity via inner product.
    """
    def __init__(self, model_name: str, normalize: bool = True):
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)
        self.normalize = normalize

    def encode(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        vecs = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=True,
            normalize_embeddings=self.normalize
        )
        return np.asarray(vecs, dtype=np.float32)
