# Contribution Guide

This repository is organized as a paper reproducibility repository. Additions
should preserve public reproducibility without exposing private runtime state.

## RAG Contributions

Place public RAG implementation code under `personaai/rag/`.

Before adding RAG files:

- Remove archive wrapper artifacts such as `.DS_Store` and `._*`.
- Remove `__pycache__`, `.pyc`, notebook checkpoints, and local scratch files.
- Exclude raw corpora, generated embeddings, vector stores, and database files.
- Replace local absolute paths with documented placeholders.
- Use example configuration files only; never commit `.env` files or real
  service credentials.
- Update `protocols/rag/` when retrieval behavior, prompt boundaries, tool
  behavior, or corpus provenance changes.

## Analysis Contributions

Place manuscript analysis materials under `analysis/` or a future `analyses/`
directory. Include deterministic scripts, small summary results, and data
manifests. Do not commit raw controlled-access data or large derived single-cell
objects.

## Protocol Contributions

Use `protocols/` for public provenance documents that explain how
agent-assisted workflow steps map to reproducible analysis logic. Protocol files
should be general enough for review while avoiding private prompts,
credentials, and internal infrastructure details.
