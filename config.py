"""Centralized configuration and startup validation for RepoLens."""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv


load_dotenv()


class ConfigError(ValueError):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class Settings:
    groq_api_key: str
    gemini_api_key: str
    qdrant_url: str
    qdrant_api_key: str
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    github_token: Optional[str]
    cloned_repos_path: str = "./cloned_repos"


REQUIRED_ENV_VARS = [
    "GROQ_API_KEY",
    "GEMINI_API_KEY",
    "QDRANT_URL",
    "QDRANT_API_KEY",
    "NEO4J_URI",
    "NEO4J_USER",
    "NEO4J_PASSWORD",
]



def _read_env(name: str, *, required: bool = True, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name, default)
    if required and (value is None or not value.strip()):
        raise ConfigError(f"Missing required environment variable: {name}")
    return value.strip() if isinstance(value, str) else value



def load_settings() -> Settings:
    """Load settings from environment and validate required values."""
    settings = Settings(
        groq_api_key=_read_env("GROQ_API_KEY"),
        gemini_api_key=_read_env("GEMINI_API_KEY"),
        qdrant_url=_read_env("QDRANT_URL"),
        qdrant_api_key=_read_env("QDRANT_API_KEY"),
        neo4j_uri=_read_env("NEO4J_URI"),
        neo4j_user=_read_env("NEO4J_USER"),
        neo4j_password=_read_env("NEO4J_PASSWORD"),
        github_token=_read_env("GITHUB_TOKEN", required=False),
        cloned_repos_path=_read_env("CLONED_REPOS_PATH", required=False, default="./cloned_repos") or "./cloned_repos",
    )

    os.makedirs(settings.cloned_repos_path, exist_ok=True)
    return settings



def _verify_qdrant(settings: Settings) -> None:
    from qdrant_client import QdrantClient

    client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key, timeout=10)
    client.get_collections()



def _verify_neo4j(settings: Settings) -> None:
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )
    try:
        driver.verify_connectivity()
    finally:
        driver.close()



def _verify_embedding_model() -> None:
    from sentence_transformers import SentenceTransformer

    SentenceTransformer("nomic-ai/nomic-embed-text-v1.5", trust_remote_code=True)



def verify_setup() -> int:
    """Validate config and external service connectivity."""
    try:
        settings = load_settings()
        print("OK: Required env vars loaded")
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1

    checks = [
        ("Groq API key", lambda: settings.groq_api_key),
        ("Gemini API key", lambda: settings.gemini_api_key),
        ("Qdrant Cloud", lambda: _verify_qdrant(settings)),
        ("Neo4j AuraDB", lambda: _verify_neo4j(settings)),
        ("Embedding model", _verify_embedding_model),
    ]

    failed = False
    for check_name, fn in checks:
        try:
            fn()
            print(f"OK: {check_name}")
        except Exception as exc:
            failed = True
            print(f"ERROR: {check_name} check failed -> {exc}")

    if failed:
        print("Setup verification completed with errors.")
        return 1

    print("Setup verification completed successfully.")
    return 0



def main() -> None:
    parser = argparse.ArgumentParser(description="RepoLens configuration helper")
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Validate env vars + service connectivity + local embedding model load.",
    )
    args = parser.parse_args()

    if args.verify:
        raise SystemExit(verify_setup())

    try:
        _ = load_settings()
        print("Configuration loaded successfully.")
    except ConfigError as exc:
        print(f"Configuration error: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
