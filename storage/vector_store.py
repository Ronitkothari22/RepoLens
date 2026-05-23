"""Qdrant vector store adapter."""

from __future__ import annotations

import re
from hashlib import blake2b
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, FieldCondition, Filter, MatchValue, PointStruct, VectorParams

from config import load_settings


def _collection_name(repo_name: str) -> str:
    """Normalize repo name to a valid Qdrant collection identifier."""
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", repo_name.strip())
    return cleaned[:255] or "default_repo"


class QdrantVectorStore:
    """Qdrant-backed vector storage for code chunks."""

    VECTOR_SIZE = 768

    def __init__(self) -> None:
        settings = load_settings()
        self.client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            timeout=30,
        )

    def create_collection(self, repo_name: str) -> str:
        """Create a per-repo collection when missing; return collection name."""
        collection_name = _collection_name(repo_name)
        existing = {c.name for c in self.client.get_collections().collections}
        if collection_name not in existing:
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=self.VECTOR_SIZE, distance=Distance.COSINE),
            )
        return collection_name

    def upsert_embeddings(self, embedded_chunks: list[tuple[str, list[float], dict]], repo_name: str) -> None:
        """Upsert embedded chunks into the repo collection."""
        if not embedded_chunks:
            return

        collection_name = self.create_collection(repo_name)
        points: list[PointStruct] = []
        for chunk_text, vector, metadata in embedded_chunks:
            payload = dict(metadata)
            payload["text"] = chunk_text
            stable_key = f"{repo_name}|{payload.get('file','')}|{payload.get('symbol_name','')}|{chunk_text[:128]}"
            point_id = int.from_bytes(blake2b(stable_key.encode("utf-8"), digest_size=8).digest(), "big")
            points.append(PointStruct(id=point_id, vector=vector, payload=payload))

        self.client.upsert(collection_name=collection_name, points=points, wait=True)

    def similarity_search(self, query_vector: list[float], repo_name: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Return top-k chunks as {text, score, metadata}."""
        collection_name = _collection_name(repo_name)
        results = self.client.search(collection_name=collection_name, query_vector=query_vector, limit=top_k)
        formatted: list[dict[str, Any]] = []
        for hit in results:
            payload = dict(hit.payload or {})
            text = payload.pop("text", "")
            formatted.append(
                {
                    "text": text,
                    "score": float(hit.score),
                    "metadata": payload,
                }
            )
        return formatted

    def fetch_by_symbol_names(
        self,
        repo_name: str,
        symbol_names: list[str],
        top_k_per_symbol: int = 3,
    ) -> list[dict[str, Any]]:
        """Fetch chunks by symbol_name payload, used by hybrid retrieval."""
        if not symbol_names:
            return []

        collection_name = _collection_name(repo_name)
        gathered: list[dict[str, Any]] = []
        for symbol_name in set(symbol_names):
            results = self.client.scroll(
                collection_name=collection_name,
                scroll_filter=Filter(
                    must=[FieldCondition(key="symbol_name", match=MatchValue(value=symbol_name))]
                ),
                limit=top_k_per_symbol,
                with_payload=True,
                with_vectors=False,
            )[0]

            for point in results:
                payload = dict(point.payload or {})
                text = payload.pop("text", "")
                gathered.append({"text": text, "score": 0.0, "metadata": payload})
        return gathered

    def delete_collection(self, repo_name: str) -> None:
        """Delete a repo collection if present."""
        collection_name = _collection_name(repo_name)
        existing = {c.name for c in self.client.get_collections().collections}
        if collection_name in existing:
            self.client.delete_collection(collection_name=collection_name)

    def list_collections(self) -> list[str]:
        """List available repo collections."""
        return [c.name for c in self.client.get_collections().collections]
