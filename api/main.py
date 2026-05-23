"""FastAPI application entrypoint."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel, Field

from config import load_settings
from ingestion.ast_parser import build_symbol_table
from ingestion.chunker import chunk_files
from ingestion.cloner import cleanup_repo, clone_repo
from ingestion.embedder import RepoEmbedder
from ingestion.parser import parse_repository
from pipeline.qa import answer_question
from pipeline.summarizer import summarize_project
from storage.graph_store import Neo4jGraphStore
from storage.vector_store import QdrantVectorStore


app = FastAPI(title="RepoLens API", version="0.1.0")


class IngestRequest(BaseModel):
    github_url: str = Field(min_length=1)


class AskRequest(BaseModel):
    repo_name: str = Field(min_length=1)
    question: str = Field(min_length=1)
    top_k: int = Field(default=8, ge=1, le=20)


class JobStatus(BaseModel):
    job_id: str
    repo_name: str
    github_url: str
    status: Literal["queued", "running", "completed", "failed"]
    created_at: str
    updated_at: str
    error: str | None = None


JOB_STORE: dict[str, JobStatus] = {}
SUMMARY_CACHE: dict[str, dict] = {}


def _repo_name_from_url(url: str) -> str:
    cleaned = url.rstrip("/").split("/")[-1]
    return cleaned[:-4] if cleaned.endswith(".git") else cleaned


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_ingestion_job(job_id: str, github_url: str, repo_name: str) -> None:
    job = JOB_STORE[job_id]
    job.status = "running"
    job.updated_at = _now_iso()
    JOB_STORE[job_id] = job

    local_path: Path | None = None
    graph_store: Neo4jGraphStore | None = None
    try:
        local_path = clone_repo(github_url)
        parsed_files = parse_repository(local_path, repo_name=repo_name)
        symbol_table = build_symbol_table(parsed_files)
        chunks = chunk_files(parsed_files, symbol_table)
        embedded = RepoEmbedder().embed_chunks(chunks)

        vector_store = QdrantVectorStore()
        vector_store.upsert_embeddings(embedded, repo_name=repo_name)

        graph_store = Neo4jGraphStore()
        graph_store.build_graph(symbol_table, repo_name=repo_name)

        SUMMARY_CACHE[repo_name] = summarize_project(repo_name)

        job.status = "completed"
        job.updated_at = _now_iso()
        JOB_STORE[job_id] = job
    except Exception as exc:
        job.status = "failed"
        job.error = str(exc)
        job.updated_at = _now_iso()
        JOB_STORE[job_id] = job
    finally:
        if graph_store is not None:
            graph_store.close()
        if local_path is not None:
            cleanup_repo(local_path)


@app.get("/health")
def health_check() -> dict:
    try:
        v = QdrantVectorStore()
        _ = v.list_collections()
        qdrant_ok = True
    except Exception as exc:
        qdrant_ok = False
        qdrant_err = str(exc)

    try:
        g = Neo4jGraphStore()
        g.close()
        neo4j_ok = True
    except Exception as exc:
        neo4j_ok = False
        neo4j_err = str(exc)

    if qdrant_ok and neo4j_ok:
        return {"status": "ok", "qdrant": "ok", "neo4j": "ok"}

    return {
        "status": "degraded",
        "qdrant": "ok" if qdrant_ok else f"error: {qdrant_err}",
        "neo4j": "ok" if neo4j_ok else f"error: {neo4j_err}",
    }


@app.post("/ingest")
def ingest_repo(payload: IngestRequest, background_tasks: BackgroundTasks) -> dict:
    repo_name = _repo_name_from_url(payload.github_url)
    if not repo_name:
        raise HTTPException(status_code=400, detail="Unable to infer repo_name from github_url")

    job_id = str(uuid4())
    now = _now_iso()
    job = JobStatus(
        job_id=job_id,
        repo_name=repo_name,
        github_url=payload.github_url,
        status="queued",
        created_at=now,
        updated_at=now,
    )
    JOB_STORE[job_id] = job
    background_tasks.add_task(_run_ingestion_job, job_id, payload.github_url, repo_name)
    return {"job_id": job_id, "repo_name": repo_name, "status": "queued"}


@app.get("/jobs/{job_id}")
def get_job_status(job_id: str) -> dict:
    job = JOB_STORE.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.model_dump()


@app.get("/summary/{repo_name}")
def get_summary(repo_name: str) -> dict:
    summary = SUMMARY_CACHE.get(repo_name)
    if not summary:
        raise HTTPException(status_code=404, detail="Summary not found. Ingest repo first.")
    return summary


@app.post("/ask")
def ask_question(payload: AskRequest) -> dict:
    try:
        return answer_question(repo_name=payload.repo_name, query=payload.question, top_k=payload.top_k)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to answer question: {exc}") from exc


@app.get("/repos")
def list_repos() -> dict:
    try:
        repos = QdrantVectorStore().list_collections()
        return {"repos": repos}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to list repos: {exc}") from exc


@app.delete("/repos/{repo_name}")
def delete_repo(repo_name: str) -> dict:
    try:
        QdrantVectorStore().delete_collection(repo_name)
        graph = Neo4jGraphStore()
        graph.delete_repo_graph(repo_name)
        graph.close()
        SUMMARY_CACHE.pop(repo_name, None)
        return {"deleted": repo_name}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to delete repo data: {exc}") from exc
