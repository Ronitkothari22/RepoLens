"""Code chunking utilities."""

from __future__ import annotations

from langchain_text_splitters import RecursiveCharacterTextSplitter


def _fallback_splitter() -> RecursiveCharacterTextSplitter:
    # ~2200 chars is a rough proxy for ~512 tokens in code-heavy text.
    return RecursiveCharacterTextSplitter(
        chunk_size=2200,
        chunk_overlap=220,
        separators=["\nclass ", "\ndef ", "\nfunction ", "\n\n", "\n", " ", ""],
    )


def chunk_files(parsed_files: list[dict], symbol_table: dict[str, dict]) -> list[dict]:
    """
    Return chunks with metadata:
    file, language, chunk_type, symbol_name, repo_name, text
    """
    chunks: list[dict] = []
    splitter = _fallback_splitter()

    for file_doc in parsed_files:
        filepath = file_doc["filepath"]
        language = file_doc["language"]
        repo_name = file_doc["repo_name"]
        content = file_doc["content"]
        symbols = symbol_table.get(filepath, {}).get("symbols", [])

        if symbols:
            for sym in symbols:
                snippet = content[sym["start_byte"] : sym["end_byte"]].strip()
                if not snippet:
                    continue
                chunks.append(
                    {
                        "text": snippet,
                        "metadata": {
                            "file": filepath,
                            "language": language,
                            "chunk_type": sym["symbol_type"],
                            "symbol_name": sym["name"],
                            "repo_name": repo_name,
                        },
                    }
                )
            continue

        for snippet in splitter.split_text(content):
            chunk_text = snippet.strip()
            if not chunk_text:
                continue
            chunks.append(
                {
                    "text": chunk_text,
                    "metadata": {
                        "file": filepath,
                        "language": language,
                        "chunk_type": "module",
                        "symbol_name": filepath,
                        "repo_name": repo_name,
                    },
                }
            )

    return chunks
