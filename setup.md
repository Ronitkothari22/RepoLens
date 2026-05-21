# External Setup Guide

> Everything in this file must be done **manually by you** before running the project.
> None of this can be automated — these are account creations, API keys, and cloud configs.

---

## 1. Python Environment

Install Python 3.10 or higher if not already installed.

```bash
python --version   # should be 3.10+
```

Create and activate a virtual environment:

```bash
python -m venv venv

# On Mac/Linux:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

---

## 2. Install Dependencies

Once inside the virtual environment:

```bash
pip install -r requirements.txt
```

Key packages that will be installed:
- `gitpython` — repo cloning
- `tree-sitter` + language bindings — AST parsing
- `sentence-transformers` — local embeddings (downloads model on first run ~500MB)
- `qdrant-client` — Qdrant Cloud vector store client
- `neo4j` — Neo4j AuraDB graph store driver
- `fastapi` + `uvicorn` — backend API
- `streamlit` — frontend UI
- `groq` — Groq API client
- `google-generativeai` — Gemini API client

---

## 3. Set Up Qdrant Cloud (Vector Store)

Qdrant Cloud is the vector database. Free tier gives 1GB forever — enough for dozens of repos.

1. Go to [https://cloud.qdrant.io](https://cloud.qdrant.io)
2. Sign up for a free account
3. Click **Create Cluster** → select the **Free** tier → pick any region
4. Once the cluster is created, go to **Access** tab
5. Copy the **Cluster URL** (looks like `https://xxxx.qdrant.io`)
6. Click **Create API Key** → copy the key

Save both — you'll need them in your `.env` file.

---

## 4. Set Up Neo4j AuraDB (Graph Store)

Neo4j AuraDB Free is the graph database. Free tier gives 200MB — sufficient for code graphs.

1. Go to [https://neo4j.com/cloud/aura](https://neo4j.com/cloud/aura)
2. Sign up for a free account
3. Click **Create a free instance**
4. Name it anything (e.g. `codebase-rag`)
5. **Important:** On the next screen, Neo4j will show you the generated password **only once** — copy it immediately
6. Wait for the instance to be ready (~2 minutes)
7. From the instance card, copy the **Connection URI** (looks like `neo4j+s://xxxx.databases.neo4j.io`)

You'll need: URI, username (`neo4j` by default), and the password you copied.

---

## 5. Get a Free Groq API Key

Groq is used for fast Q&A responses (Llama 3.1 70B).

1. Go to [https://console.groq.com](https://console.groq.com)
2. Sign up for a free account
3. Navigate to **API Keys** → click **Create API Key**
4. Copy the key — you will only see it once

Free tier limits: **30 requests/minute**, **14,400 requests/day** — more than enough.

---

## 6. Get a Free Google Gemini API Key

Gemini Flash is used for long-context project summarization.

1. Go to [https://aistudio.google.com](https://aistudio.google.com)
2. Sign in with your Google account
3. Click **Get API Key** → **Create API key in new project**
4. Copy the key

Free tier limits: **15 requests/minute**, **1 million tokens/day** — very generous.

---

## 7. (Optional) GitHub Personal Access Token

Required only if you want to ingest **private repositories**.

1. Go to [https://github.com/settings/tokens](https://github.com/settings/tokens)
2. Click **Generate new token (classic)**
3. Select scope: `repo` (full repo access)
4. Copy the token

For public repos only, you can skip this step.

---

## 8. Create Your `.env` File

In the root of the project, create a file named `.env` (copy from `.env.example`):

```bash
cp .env.example .env
```

Then open `.env` and fill in all your keys:

```env
# LLM APIs
GROQ_API_KEY=your_groq_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here

# Qdrant Cloud (Vector Store)
QDRANT_URL=https://xxxx.qdrant.io
QDRANT_API_KEY=your_qdrant_api_key_here

# Neo4j AuraDB (Graph Store)
NEO4J_URI=neo4j+s://xxxx.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_neo4j_password_here

# GitHub (optional — only for private repos)
GITHUB_TOKEN=your_github_token_here

# Temp path for cloning repos (cleaned up after ingestion)
CLONED_REPOS_PATH=./cloned_repos
```

**Never commit `.env` to git.** It is already in `.gitignore`.

---

## 9. Install tree-sitter Language Bindings

tree-sitter requires language grammars. Run this once after installing dependencies:

```bash
pip install tree-sitter-python tree-sitter-javascript tree-sitter-typescript
```

---

## 10. First Run — Embedding Model Download

The first time you run the project, `sentence-transformers` will automatically download the `nomic-ai/nomic-embed-text-v1.5` model (~500MB). This is a one-time download cached locally.

Make sure you have a stable internet connection and ~1GB free disk space before first run.

---

## 11. Verify Everything Works

Run this quick check to confirm all services are connected:

```bash
python config.py --verify
```

Expected output:
```
✅ Groq API key found
✅ Gemini API key found
✅ Qdrant Cloud connected — cluster reachable
✅ Neo4j AuraDB connected — instance reachable
✅ Embedding model loaded
✅ Setup complete
```

---

## 12. Running Locally

Start the FastAPI backend:

```bash
uvicorn api.main:app --reload --port 8000
```

In a separate terminal, start the Streamlit frontend:

```bash
streamlit run ui/app.py
```

Open your browser at `http://localhost:8501`

---

## 13. Deploying to Render

Both Qdrant Cloud and Neo4j AuraDB are already cloud-hosted, so Render deployment is straightforward.

1. Push your code to a GitHub repo
2. Go to [https://render.com](https://render.com) → **New Web Service** → connect your repo
3. Set **Start Command** to:
   ```
   uvicorn api.main:app --host 0.0.0.0 --port $PORT
   ```
4. Go to **Environment** tab in Render and add all the same env vars from your `.env` file:
   - `GROQ_API_KEY`
   - `GEMINI_API_KEY`
   - `QDRANT_URL`
   - `QDRANT_API_KEY`
   - `NEO4J_URI`
   - `NEO4J_USER`
   - `NEO4J_PASSWORD`
   - `GITHUB_TOKEN` (if using private repos)
5. Deploy — Render will install dependencies from `requirements.txt` automatically
6. For the Streamlit frontend, create a second Render web service pointing to `streamlit run ui/app.py --server.port $PORT --server.address 0.0.0.0`

**Note:** Do not add `CHROMA_DB_PATH` or any local storage paths — we are not using local storage anymore.

---

## Summary Checklist

- [ ] Python 3.10+ installed
- [ ] Virtual environment created and activated
- [ ] `pip install -r requirements.txt` done
- [ ] Qdrant Cloud cluster created — URL and API key copied
- [ ] Neo4j AuraDB instance created — URI and password copied
- [ ] Groq API key obtained and added to `.env`
- [ ] Gemini API key obtained and added to `.env`
- [ ] GitHub token added (optional, for private repos)
- [ ] `.env` file created and fully filled in
- [ ] tree-sitter language bindings installed
- [ ] ~1GB disk space free for embedding model cache