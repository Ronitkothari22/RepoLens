"""Hybrid retrieval orchestration."""

from __future__ import annotations

from typing import Any

from ingestion.embedder import RepoEmbedder
from storage.graph_store import Neo4jGraphStore
from storage.vector_store import QdrantVectorStore


def _chunk_key(item: dict[str, Any]) -> tuple[str, str]:
    metadata = item.get("metadata", {})
    return (metadata.get("file", ""), metadata.get("symbol_name", ""))


def hybrid_search(query: str, repo_name: str, top_k: int = 8) -> list[dict[str, Any]]:
    """
    Hybrid retrieval:
    1) Vector similarity over code chunks
    2) Graph neighborhood expansion via symbol relationships
    3) Merge + deduplicate + weighted rerank
    """
    embedder = RepoEmbedder()
    vector_store = QdrantVectorStore()
    graph_store = Neo4jGraphStore()

    try:
        query_vector = embedder.model.encode(
            [query],
            batch_size=1,
            show_progress_bar=False,
            normalize_embeddings=True,
        )[0].tolist()

        vector_hits = vector_store.similarity_search(query_vector=query_vector, repo_name=repo_name, top_k=top_k)
        symbols = [
            hit.get("metadata", {}).get("symbol_name")
            for hit in vector_hits
            if hit.get("metadata", {}).get("symbol_name")
        ]

        neighbor_symbols: list[str] = []
        for symbol in set(symbols):
            neighbors = graph_store.get_neighbors(symbol_name=symbol, repo_name=repo_name, depth=2)
            for node in neighbors:
                value = node.get("value")
                if isinstance(value, str) and value:
                    neighbor_symbols.append(value)

        graph_hits = vector_store.fetch_by_symbol_names(
            repo_name=repo_name,
            symbol_names=neighbor_symbols,
            top_k_per_symbol=2,
        )

        merged: dict[tuple[str, str], dict[str, Any]] = {}
        for item in vector_hits:
            key = _chunk_key(item)
            merged[key] = {
                "text": item.get("text", ""),
                "metadata": item.get("metadata", {}),
                "score": float(item.get("score", 0.0)),
            }

        graph_boost = 0.08
        for item in graph_hits:
            key = _chunk_key(item)
            if key in merged:
                merged[key]["score"] += graph_boost
            else:
                merged[key] = {
                    "text": item.get("text", ""),
                    "metadata": item.get("metadata", {}),
                    "score": graph_boost,
                }

        ranked = sorted(merged.values(), key=lambda x: x["score"], reverse=True)
        return ranked[:top_k]
    finally:
        graph_store.close()
