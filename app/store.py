"""A small, dependency-light vector store backed by a NumPy matrix on disk."""
from __future__ import annotations

import numpy as np

from .config import INDEX_PATH


class VectorStore:
    def __init__(self, matrix: np.ndarray | None = None):
        self.matrix = matrix  # shape (n_chunks, dim), L2-normalised rows

    @property
    def ready(self) -> bool:
        return self.matrix is not None and self.matrix.size > 0

    @staticmethod
    def _normalise(a: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(a, axis=-1, keepdims=True)
        return a / np.clip(norms, 1e-10, None)

    def build(self, vectors: list[list[float]]) -> None:
        self.matrix = self._normalise(np.asarray(vectors, dtype=np.float32))

    def search(self, query_vec: list[float], top_k: int) -> list[tuple[int, float]]:
        """Return (chunk_id, cosine_similarity) pairs, best first."""
        if not self.ready:
            return []
        q = self._normalise(np.asarray(query_vec, dtype=np.float32))
        scores = self.matrix @ q
        k = min(top_k, scores.shape[0])
        top = np.argpartition(-scores, k - 1)[:k]
        top = top[np.argsort(-scores[top])]
        return [(int(i), float(scores[i])) for i in top]

    def save(self) -> None:
        if self.ready:
            np.savez_compressed(INDEX_PATH, matrix=self.matrix)

    @classmethod
    def load(cls) -> "VectorStore":
        if INDEX_PATH.exists():
            with np.load(INDEX_PATH) as z:
                return cls(z["matrix"])
        return cls()
