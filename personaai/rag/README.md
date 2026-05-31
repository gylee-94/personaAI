# PersonaAI RAG

This directory contains the backend-only Retrieval-Augmented Generation (RAG)
implementation used for the PersonaAI paper workflow. The system is a
LangGraph-based agent over an aging literature corpus of approximately 566,000
XML documents, with query expansion, dense retrieval and reranking,
draft-answer generation, self-evaluation, and an optional web-search fallback.

The graph is defined in `backend/agent/graph.py` and exposed through
`langgraph.json`. This public release intentionally excludes raw retrieval
corpus files, generated vector stores, runtime `.env` files, API keys, and local
deployment state.

## Contents

```text
personaai/rag/
  backend/
    agent/
    tools/
    prompts/
    .env.example
  run_full_indexing.py
  langgraph.json
  Dockerfile.backend
  docker-compose.yml
  pyproject.toml
  uv.lock
```

## Configuration

Backend configuration is read from `backend/.env`, which is intentionally
git-ignored. Start from the public template:

```bash
cp backend/.env.example backend/.env
```

Required provider and retrieval settings include:

| Variable | Description |
|----------|-------------|
| `OPENROUTER_API_KEY` | OpenRouter API key for the chat LLM |
| `OPENROUTER_MODEL` | OpenRouter model id |
| `TAVILY_API_KEY` | Tavily key for optional web-search fallback |
| `QDRANT_HOST`, `QDRANT_PORT`, `QDRANT_COLLECTION` | Qdrant vector-store connection |
| `EMBEDDING_MODEL`, `EMBEDDING_BATCH_SIZE` | Embedding model and indexing batch size |
| `RERANKER_MODEL_PATH`, `RERANKER_TOP_N` | Reranker configuration |
| `DATA_DIR` | Local source corpus directory for indexing |

Raw corpus files and generated vector stores are not redistributed. Corpus
provenance is summarized in `../../protocols/rag/retrieval_corpus_manifest.tsv`.

## Docker Backend Run

The Docker Compose setup runs Qdrant and the LangGraph backend only.

```bash
cd personaai/rag
cp backend/.env.example backend/.env
# edit backend/.env with API keys and runtime settings
docker compose up --build
```

Services:

| Service | URL | Notes |
|---------|-----|-------|
| LangGraph API | `http://localhost:2024` | RAG backend graph endpoint |
| Qdrant dashboard | `http://localhost:6333/dashboard` | Optional vector-store inspection |

Populate the Qdrant collection once after placing the local corpus under
`./data`, which is mounted to `/data` in the container:

```bash
docker compose run --rm backend uv run python run_full_indexing.py
```

Until indexing completes, the agent can run but will not retrieve corpus
context.

## Local Backend Run

Prerequisites:

| Component | Version / Notes |
|-----------|-----------------|
| Python | 3.12, pinned by `.python-version` |
| `uv` | Python environment and dependency manager |
| Qdrant | Running locally or reachable through `QDRANT_HOST` / `QDRANT_PORT` |
| GPU | Recommended for embedding and reranker models |

Start Qdrant:

```bash
docker run -p 6333:6333 -p 6334:6334 qdrant/qdrant:v1.16.0
```

Install and run the backend:

```bash
cd personaai/rag
uv sync --locked
uv run langgraph dev
```

Run a standalone graph smoke test:

```bash
uv run python -m backend.agent.graph
```

Index the local corpus:

```bash
uv run python run_full_indexing.py
```

## Indexing

`run_full_indexing.py` scans `DATA_DIR` recursively for `.xml` files, extracts
academic metadata such as title, authors, journal, DOI, PMID, and PMCID when
available, embeds document chunks with `EMBEDDING_MODEL`, and upserts the
vectors and chunk metadata into `QDRANT_COLLECTION`.

PMID and PMCID are not embedded as separate standalone vectors. They are stored
as metadata payload fields attached to the embedded text chunks, and are used
for source display and citation formatting in retrieved results.

These settings must match between indexing and serving:

| Setting | Why it must match |
|---------|-------------------|
| `QDRANT_COLLECTION` | The agent queries exactly the collection written by indexing |
| `EMBEDDING_MODEL` | Query and document vectors must use the same model |
| Vector dimension | Fixed at collection creation time |

To switch embedding models, index into a new, empty collection.

## Prompts and Domain Adaptation

The prompts in this repository are specialized for the paper workflow and the
aging biomedical literature corpus. To adapt the RAG system to a different
corpus, update both the indexed corpus and the domain-specific prompt blocks in
`backend/agent/nodes.py`.

Relevant prompt-bearing nodes include:

- `intent_analysis_node`
- `expand_query_node`
- `direct_answer`
- `generate_answer_node`
- `evaluate_answer_node`

## Reproducibility

To recreate the Python environment:

```bash
uv sync --locked
```

The interpreter is pinned by `.python-version`, direct dependencies are listed
in `pyproject.toml`, and the resolved dependency graph is locked in `uv.lock`.

## Public Release Boundary

Do not commit:

- `backend/.env`
- raw retrieval corpora
- generated embeddings or vector stores
- Qdrant storage
- API keys or service credentials
- local runtime logs or deployment state
