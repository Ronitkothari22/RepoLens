"""Streamlit app entrypoint."""

from __future__ import annotations

import json
import time
from typing import Any
from urllib import error, request

import streamlit as st


API_BASE_DEFAULT = "http://127.0.0.1:8000"


def _api_call(method: str, path: str, body: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
    url = f"{st.session_state.api_base.rstrip('/')}{path}"
    payload = None if body is None else json.dumps(body).encode("utf-8")
    req = request.Request(url=url, data=payload, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with request.urlopen(req, timeout=120) as resp:
            data = resp.read().decode("utf-8")
            return resp.status, json.loads(data) if data else {}
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            return exc.code, json.loads(raw) if raw else {"detail": str(exc)}
        except json.JSONDecodeError:
            return exc.code, {"detail": raw or str(exc)}
    except Exception as exc:
        return 0, {"detail": str(exc)}


def _init_state() -> None:
    st.session_state.setdefault("api_base", API_BASE_DEFAULT)
    st.session_state.setdefault("job_id", "")
    st.session_state.setdefault("repo_name", "")
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("last_summary", None)


def _render_sources(sources: list[str]) -> None:
    if not sources:
        return
    st.caption("Sources")
    for src in sources:
        st.write(f"- `{src}`")


def main() -> None:
    st.set_page_config(page_title="RepoLens", page_icon=":mag:", layout="wide")
    _init_state()

    st.title("RepoLens")
    st.caption("Codebase RAG: ingest GitHub repositories, summarize architecture, and ask grounded questions.")

    with st.sidebar:
        st.subheader("Settings")
        st.session_state.api_base = st.text_input("API Base URL", value=st.session_state.api_base)
        if st.button("Refresh Repos"):
            st.rerun()

    st.subheader("Ingest Repository")
    github_url = st.text_input("GitHub URL", placeholder="https://github.com/owner/repo.git")
    if st.button("Ingest", type="primary", disabled=not github_url.strip()):
        code, resp = _api_call("POST", "/ingest", {"github_url": github_url.strip()})
        if code == 200:
            st.session_state.job_id = resp.get("job_id", "")
            st.session_state.repo_name = resp.get("repo_name", "")
            st.success(f"Ingestion queued for `{st.session_state.repo_name}`")
        else:
            st.error(f"Ingest failed: {resp.get('detail', resp)}")

    if st.session_state.job_id:
        with st.spinner("Ingestion in progress..."):
            for _ in range(60):
                code, status_resp = _api_call("GET", f"/jobs/{st.session_state.job_id}")
                if code != 200:
                    st.warning(f"Unable to read job status: {status_resp.get('detail', status_resp)}")
                    break
                status = status_resp.get("status")
                if status == "completed":
                    st.success(f"Ingestion completed for `{status_resp.get('repo_name', st.session_state.repo_name)}`")
                    st.session_state.job_id = ""
                    break
                if status == "failed":
                    st.error(f"Ingestion failed: {status_resp.get('error', 'unknown error')}")
                    st.session_state.job_id = ""
                    break
                time.sleep(2)

    st.subheader("Repository Summary")
    repos_code, repos_resp = _api_call("GET", "/repos")
    repos = repos_resp.get("repos", []) if repos_code == 200 else []
    if repos_code != 200:
        st.warning(f"Could not fetch repos: {repos_resp.get('detail', repos_resp)}")
    selected_repo = st.selectbox(
        "Select Repository",
        options=repos,
        index=repos.index(st.session_state.repo_name) if st.session_state.repo_name in repos else 0 if repos else None,
        placeholder="No repositories ingested yet",
    )
    if selected_repo:
        st.session_state.repo_name = selected_repo
        if st.button("Load Summary"):
            code, resp = _api_call("GET", f"/summary/{selected_repo}")
            if code == 200:
                st.session_state.last_summary = resp
            else:
                st.error(f"Summary unavailable: {resp.get('detail', resp)}")

    if st.session_state.last_summary:
        st.json(st.session_state.last_summary)

    st.subheader("Ask Questions")
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            _render_sources(msg.get("sources", []))

    question = st.chat_input("Ask a question about the selected repository...")
    if question:
        if not st.session_state.repo_name:
            st.error("Select a repository first.")
        else:
            st.session_state.messages.append({"role": "user", "content": question})
            with st.chat_message("user"):
                st.markdown(question)

            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    code, resp = _api_call(
                        "POST",
                        "/ask",
                        {"repo_name": st.session_state.repo_name, "question": question, "top_k": 8},
                    )
                if code == 200:
                    answer = resp.get("answer", "")
                    sources = resp.get("sources", [])
                    st.markdown(answer)
                    _render_sources(sources)
                    st.session_state.messages.append({"role": "assistant", "content": answer, "sources": sources})
                else:
                    err = resp.get("detail", resp)
                    st.error(f"Q&A failed: {err}")
                    st.session_state.messages.append({"role": "assistant", "content": f"Error: {err}", "sources": []})


if __name__ == "__main__":
    main()
