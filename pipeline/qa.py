"""Question-answering pipeline."""

from __future__ import annotations

from pipeline.llm_client import LLMClient
from retrieval.hybrid import hybrid_search


def _build_qa_prompt(question: str, repo_name: str, retrieved_chunks: list[dict]) -> str:
    context_parts: list[str] = []
    for idx, chunk in enumerate(retrieved_chunks, start=1):
        meta = chunk.get("metadata", {})
        context_parts.append(
            "\n".join(
                [
                    f"[Chunk {idx}]",
                    f"file: {meta.get('file', '')}",
                    f"symbol: {meta.get('symbol_name', '')}",
                    f"score: {chunk.get('score', 0.0):.4f}",
                    chunk.get("text", ""),
                ]
            )
        )

    joined_context = "\n\n".join(context_parts) if context_parts else "(no retrieval context found)"
    return f"""
You are a precise codebase assistant. Answer using only the provided repository context.
If the context is insufficient, say so clearly.

Repository: {repo_name}

Retrieved Context:
{joined_context}

User Question:
{question}

Response requirements:
- Give a direct answer first.
- Keep it concise and technical.
- Include a short "Sources" section listing relevant file paths only.
""".strip()


def answer_question(repo_name: str, query: str, top_k: int = 8) -> dict:
    """Run hybrid retrieval and answer question with Groq."""
    chunks = hybrid_search(query=query, repo_name=repo_name, top_k=top_k)
    prompt = _build_qa_prompt(question=query, repo_name=repo_name, retrieved_chunks=chunks)
    llm = LLMClient()
    answer = llm.call_llm(prompt, task_type="qa")

    sources: list[str] = []
    seen: set[str] = set()
    for chunk in chunks:
        file_path = chunk.get("metadata", {}).get("file")
        if isinstance(file_path, str) and file_path and file_path not in seen:
            seen.add(file_path)
            sources.append(file_path)

    return {
        "repo_name": repo_name,
        "question": query,
        "answer": answer,
        "sources": sources,
        "chunks": chunks,
    }
