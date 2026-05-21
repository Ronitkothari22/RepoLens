# Codebase RAG — Task List

## Phase 1 — Project Scaffolding

- [ ] Initialize project folder structure as per architecture
- [ ] Create `requirements.txt` with all dependencies
- [ ] Create `.env.example` with all required env vars (`GROQ_API_KEY`, `GEMINI_API_KEY`, `QDRANT_URL`, `QDRANT_API_KEY`, `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, `GITHUB_TOKEN`)
- [ ] Create `config.py` to load and validate all env vars on startup
- [ ] Add `.gitignore` (ignore `cloned_repos/`, `.env`, `__pycache__/`, `venv/`)

---

## Phase 2 — Ingestion Pipeline

### 2.1 Repo Cloner (`ingestion/cloner.py`)
- [ ] Accept a GitHub URL as input
- [ ] Clone the repo into a local temp directory using `gitpython`
- [ ] Support both public and private repos (token-based auth via `GITHUB_TOKEN` env var)
- [ ] Return the local path of the cloned repo
- [ ] Clean up cloned repo from disk after ingestion is complete to save space

### 2.2 File Parser (`ingestion/parser.py`)
- [ ] Walk the cloned repo directory recursively
- [ ] Filter only code files by extension (`.py`, `.js`, `.ts`, `.go`, `.java`, `.cpp`, `.rs`, `.md`, etc.)
- [ ] Skip irrelevant dirs: `node_modules/`, `.git/`, `dist/`, `build/`, `__pycache__/`, `venv/`
- [ ] Read file content and store with metadata: `filepath`, `language`, `repo_name`
- [ ] Detect language from file extension

### 2.3 AST Parser (`ingestion/ast_parser.py`)
- [ ] Integrate `tree-sitter` for multi-language AST parsing
- [ ] Extract functions, classes, and imports from each file
- [ ] Build a per-file symbol table: `{file: {functions: [], classes: [], imports: []}}`
- [ ] Gracefully fall back to raw text if tree-sitter fails for a language
- [ ] Support at minimum: Python, JavaScript, TypeScript

### 2.4 Chunker (`ingestion/chunker.py`)
- [ ] Chunk by function/class boundaries (from AST output) — not arbitrary token windows
- [ ] Fall back to `RecursiveCharacterTextSplitter` with code separators for unsupported langs
- [ ] Set chunk size ~512 tokens, overlap ~50 tokens
- [ ] Attach metadata to each chunk: `file`, `language`, `chunk_type` (function/class/module), `symbol_name`

### 2.5 Embedder (`ingestion/embedder.py`)
- [ ] Load `nomic-ai/nomic-embed-text-v1.5` via `sentence-transformers` (local, free)
- [ ] Batch embed all chunks
- [ ] Return list of `(chunk_text, embedding_vector, metadata)` tuples

---

## Phase 3 — Storage Layer

### 3.1 Vector Store — Qdrant Cloud (`storage/vector_store.py`)
- [ ] Connect to Qdrant Cloud using `QDRANT_URL` and `QDRANT_API_KEY` from env
- [ ] Create a collection per repo (named by `repo_name`) with cosine distance metric and vector size 768 (nomic model output)
- [ ] Check if collection already exists before creating — skip if so
- [ ] Upsert chunks with embedding vectors and metadata payload
- [ ] Implement `similarity_search(query_vector, repo_name, top_k=5)` returning chunks + scores
- [ ] Implement `delete_collection(repo_name)` for cleanup
- [ ] Implement `list_collections()` to list all ingested repos

### 3.2 Graph Store — Neo4j AuraDB (`storage/graph_store.py`)
- [ ] Connect to Neo4j AuraDB using `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` from env
- [ ] Define node labels: `File`, `Function`, `Class`
- [ ] Define relationship types: `IMPORTS`, `CALLS`, `DEFINES`, `INHERITS`
- [ ] Add `repo_name` property to all nodes for multi-repo isolation
- [ ] Build graph from AST parser symbol tables using Cypher `MERGE` (idempotent upserts)
- [ ] Implement `get_neighbors(symbol_name, repo_name, depth=2)` using Cypher traversal
- [ ] Implement `get_callers(function_name, repo_name)` — find what calls a function
- [ ] Implement `get_callees(function_name, repo_name)` — find what a function calls
- [ ] Implement `delete_repo_graph(repo_name)` to remove all nodes for a repo
- [ ] Close driver connection cleanly on shutdown

---

## Phase 4 — Hybrid Retriever

### 4.1 Hybrid Retrieval (`retrieval/hybrid.py`)
- [ ] Implement `hybrid_search(query, repo_name, top_k=8)`:
  - Embed the query using the same `nomic-embed-text-v1.5` model
  - Run vector similarity search on Qdrant → get top-k chunks with scores
  - Extract `symbol_name` from each returned chunk's metadata
  - Query Neo4j for graph neighbors of each symbol (depth=2)
  - Fetch neighbor chunks from Qdrant by filtering on `symbol_name` metadata
  - Merge and deduplicate all chunks
  - Re-rank by weighted score: vector similarity score + small boost for graph-connected chunks
- [ ] Return final ranked list of chunks with metadata (file, symbol, score)

---

## Phase 5 — LLM Pipelines

### 5.1 Project Summarizer (`pipeline/summarizer.py`)
- [ ] Collect: README, entry-point files, `package.json`/`requirements.txt`/`Cargo.toml`, directory tree
- [ ] Build a structured prompt with all collected context
- [ ] Call Gemini Flash API (free tier) for long-context summarization
- [ ] Parse and return structured summary:
  - Project purpose
  - Tech stack
  - Architecture overview
  - Key modules/directories
  - Notable patterns or design choices

### 5.2 Q&A Chain (`pipeline/qa.py`)
- [ ] Accept `query` and `repo_name` as inputs
- [ ] Call `hybrid_search` to retrieve relevant chunks
- [ ] Build prompt: system context + retrieved chunks + user question
- [ ] Call Groq API (Llama 3.1 70B, free tier) for answer generation
- [ ] Return answer with source file references

### 5.3 LLM Client (`pipeline/llm_client.py`)
- [ ] Groq client wrapper with retry logic and error handling
- [ ] Gemini client wrapper with retry logic and error handling
- [ ] Single `call_llm(prompt, task_type)` interface — routes to Groq for Q&A, Gemini for summarization

---

## Phase 6 — API Layer

### 6.1 FastAPI Backend (`api/main.py`)
- [ ] `POST /ingest` — accepts `{ "github_url": "..." }`, runs full ingestion pipeline as background task, returns job status
- [ ] `GET /summary/{repo_name}` — returns cached project summary
- [ ] `POST /ask` — accepts `{ "repo_name": "...", "question": "..." }`, returns answer + sources
- [ ] `GET /repos` — list all ingested repos (from Qdrant collections)
- [ ] `DELETE /repos/{repo_name}` — delete repo data from both Qdrant and Neo4j
- [ ] Add background task support for ingestion (non-blocking)
- [ ] Add basic error handling and validation with Pydantic models
- [ ] Health check endpoint `GET /health` — verifies Qdrant and Neo4j connections

---

## Phase 7 — Frontend (Streamlit MVP)

### 7.1 UI (`ui/app.py`)
- [ ] Input field for GitHub URL + "Ingest" button
- [ ] Show ingestion progress / spinner
- [ ] Display project summary card after ingestion
- [ ] Dropdown to select ingested repo
- [ ] Chat-style Q&A interface with message history
- [ ] Show source file references alongside answers
- [ ] Basic session state management

---

## Phase 8 — Deployment (Render)

- [ ] Create `render.yaml` with web service config for FastAPI backend
- [ ] Set all env vars in Render dashboard (never in code): `GROQ_API_KEY`, `GEMINI_API_KEY`, `QDRANT_URL`, `QDRANT_API_KEY`, `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`
- [ ] Create `Procfile` or start command: `uvicorn api.main:app --host 0.0.0.0 --port $PORT`
- [ ] Deploy Streamlit frontend as a second Render web service
- [ ] Verify Qdrant Cloud and Neo4j AuraDB are reachable from Render on deploy

---

## Phase 9 — Testing & Polish

- [ ] Write unit tests for chunker (correct boundaries, no split mid-function)
- [ ] Write unit tests for graph builder (edges correctly represent imports)
- [ ] Write integration test: full pipeline on a small public repo
- [ ] Add logging throughout ingestion and retrieval pipelines
- [ ] Add a `--dry-run` flag to ingestion for testing without LLM calls
- [ ] Document all public functions with docstrings
- [ ] Final README with usage instructions

---

## Folder Structure Reference

```
codebase-rag/
├── ingestion/
│   ├── cloner.py
│   ├── parser.py
│   ├── ast_parser.py
│   ├── chunker.py
│   └── embedder.py
├── storage/
│   ├── vector_store.py      # Qdrant Cloud
│   └── graph_store.py       # Neo4j AuraDB
├── retrieval/
│   └── hybrid.py
├── pipeline/
│   ├── summarizer.py
│   ├── qa.py
│   └── llm_client.py
├── api/
│   └── main.py
├── ui/
│   └── app.py
├── tests/
├── config.py
├── requirements.txt
├── render.yaml
├── .env.example
└── README.md
```