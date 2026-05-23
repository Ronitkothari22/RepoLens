"""Project summarization pipeline."""

from __future__ import annotations

from pathlib import Path

from config import load_settings
from pipeline.llm_client import LLMClient


def _read_text(path: Path, max_chars: int = 12000) -> str:
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
    return content[:max_chars]


def _repo_tree(root: Path, max_entries: int = 250) -> str:
    lines: list[str] = []
    for idx, path in enumerate(sorted(root.rglob("*"))):
        if idx >= max_entries:
            lines.append("... (truncated)")
            break
        if any(part in {".git", "node_modules", "dist", "build", "venv", "__pycache__"} for part in path.parts):
            continue
        rel = path.relative_to(root)
        if path.is_dir():
            lines.append(f"{rel}/")
        else:
            lines.append(str(rel))
    return "\n".join(lines)


def _find_first_existing(root: Path, candidates: list[str]) -> Path | None:
    for candidate in candidates:
        path = root / candidate
        if path.exists() and path.is_file():
            return path
    return None


def build_summary_prompt(repo_name: str) -> str:
    """Collect context and build a structured summarization prompt."""
    settings = load_settings()
    repo_root = Path(settings.cloned_repos_path) / repo_name
    if not repo_root.exists():
        raise FileNotFoundError(f"Repository path not found for summarization: {repo_root}")

    readme_path = _find_first_existing(repo_root, ["README.md", "README", "readme.md"])
    reqs_path = _find_first_existing(repo_root, ["requirements.txt", "package.json", "Cargo.toml", "pyproject.toml"])
    entry_path = _find_first_existing(
        repo_root,
        ["main.py", "app.py", "server.py", "index.js", "index.ts", "src/main.py", "src/index.ts", "src/index.js"],
    )

    readme_text = _read_text(readme_path) if readme_path else ""
    deps_text = _read_text(reqs_path) if reqs_path else ""
    entry_text = _read_text(entry_path) if entry_path else ""
    tree_text = _repo_tree(repo_root)

    return f"""
You are an expert software architect. Analyze the repository context and return a concise, structured summary.

Repository: {repo_name}

Directory Tree:
{tree_text}

README:
{readme_text or "(missing)"}

Dependency / Manifest File ({reqs_path.name if reqs_path else "missing"}):
{deps_text or "(missing)"}

Entry Point File ({entry_path.name if entry_path else "missing"}):
{entry_text or "(missing)"}

Return JSON with keys:
- project_purpose
- tech_stack
- architecture_overview
- key_modules
- notable_patterns
""".strip()


def summarize_project(repo_name: str) -> dict:
    """Generate a structured project summary using Gemini Flash."""
    prompt = build_summary_prompt(repo_name)
    llm = LLMClient()
    raw = llm.call_llm(prompt, task_type="summarization")
    return {"repo_name": repo_name, "summary": raw}
