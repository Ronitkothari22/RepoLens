"""Repository file parsing utilities."""

from __future__ import annotations

from pathlib import Path

EXTENSION_LANGUAGE_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".java": "java",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".rs": "rust",
    ".md": "markdown",
}

SKIP_DIRS = {"node_modules", ".git", "dist", "build", "__pycache__", "venv"}


def detect_language(file_path: Path) -> str | None:
    """Infer language from extension."""
    return EXTENSION_LANGUAGE_MAP.get(file_path.suffix.lower())


def parse_repository(repo_path: str | Path, repo_name: str) -> list[dict]:
    """
    Parse supported files in a repository and return their contents + metadata.

    Returns each item as:
    {
      "filepath": "<repo-relative path>",
      "language": "<language>",
      "repo_name": "<repo_name>",
      "content": "<file text>",
    }
    """
    root = Path(repo_path).resolve()
    parsed_files: list[dict] = []

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue

        language = detect_language(path)
        if not language:
            continue

        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        parsed_files.append(
            {
                "filepath": str(path.relative_to(root)),
                "language": language,
                "repo_name": repo_name,
                "content": content,
            }
        )

    return parsed_files
