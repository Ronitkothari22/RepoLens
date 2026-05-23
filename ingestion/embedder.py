"""Embedding utilities."""

from __future__ import annotations

from sentence_transformers import SentenceTransformer


class RepoEmbedder:
    """SentenceTransformer wrapper for chunk embeddings."""

    def __init__(self, model_name: str = "nomic-ai/nomic-embed-text-v1.5") -> None:
        self.model = SentenceTransformer(model_name, trust_remote_code=True)

    def embed_chunks(self, chunks: list[dict], batch_size: int = 32) -> list[tuple[str, list[float], dict]]:
        """Embed chunk text and return (text, vector, metadata) tuples."""
        if not chunks:
            return []

        texts = [chunk["text"] for chunk in chunks]
        vectors = self.model.encode(texts, batch_size=batch_size, show_progress_bar=False, normalize_embeddings=True)
        return [
            (chunk["text"], vector.tolist(), chunk["metadata"])
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
