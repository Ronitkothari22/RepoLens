"""Repository cloning utilities."""

from __future__ import annotations

import shutil
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from git import Repo

from config import load_settings


def _repo_name_from_url(github_url: str) -> str:
    path = urlparse(github_url).path.strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    return path.split("/")[-1]


def _build_authenticated_url(github_url: str, token: str | None) -> str:
    if not token:
        return github_url
    parsed = urlparse(github_url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname != "github.com":
        return github_url
    netloc = f"{token}@{parsed.netloc}"
    return urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))


def clone_repo(github_url: str) -> Path:
    """Clone a GitHub repo and return its local path."""
    settings = load_settings()
    repo_name = _repo_name_from_url(github_url)
    clone_root = Path(settings.cloned_repos_path)
    clone_root.mkdir(parents=True, exist_ok=True)
    target = clone_root / repo_name

    if target.exists():
        shutil.rmtree(target, ignore_errors=True)

    auth_url = _build_authenticated_url(github_url, settings.github_token)
    Repo.clone_from(auth_url, target)
    return target


def cleanup_repo(local_path: str | Path) -> None:
    """Delete a cloned local repository after ingestion."""
    shutil.rmtree(Path(local_path), ignore_errors=True)
