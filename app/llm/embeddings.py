"""
Embedding Model
Uses sentence-transformers locally for semantic search.
Groq is NOT used for embeddings.
"""
import logging
from typing import List, Optional

import numpy as np

logger = logging.getLogger(__name__)

_embedder = None
_EMBEDDING_MODEL = "all-MiniLM-L6-v2"


def get_embedder():
    """Lazy-load the sentence transformer model."""
    global _embedder
    if _embedder is None:
        try:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading embedding model: %s", _EMBEDDING_MODEL)
            _embedder = SentenceTransformer(_EMBEDDING_MODEL)
            logger.info("Embedding model loaded.")
        except ImportError:
            logger.warning(
                "sentence-transformers not installed. Using zero-vector fallback."
            )
            _embedder = _FallbackEmbedder()
    return _embedder


def embed_text(text: str) -> List[float]:
    """Embed a single text string into a vector."""
    embedder = get_embedder()
    if isinstance(embedder, _FallbackEmbedder):
        return embedder.encode(text)
    vec = embedder.encode(text, convert_to_numpy=True)
    return vec.tolist()


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Embed a batch of texts."""
    embedder = get_embedder()
    if isinstance(embedder, _FallbackEmbedder):
        return [embedder.encode(t) for t in texts]
    vecs = embedder.encode(texts, convert_to_numpy=True)
    return vecs.tolist()


class _FallbackEmbedder:
    """Returns a deterministic zero vector when the real model is unavailable."""
    DIM = 384

    def encode(self, text: str) -> List[float]:
        # Deterministic hash-based "embedding" for testing
        h = hash(text) % 1000
        vec = [0.0] * self.DIM
        vec[h % self.DIM] = 1.0
        return vec
