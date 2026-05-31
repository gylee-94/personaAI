# RAG Prompt and Tool Disclosure

This document records the public disclosure boundary for RAG prompts and tools.

## Prompt Boundary

Public prompt templates may be included when they are intentionally approved for
release and do not contain private operational instructions, credentials,
internal URLs, or unpublished data.

Private prompts should be summarized at the protocol level rather than copied
verbatim.

## Tool Boundary

Public RAG tools may include retrieval, reranking, document parsing, citation
formatting, and context assembly utilities. Tools that require API-backed
services should use environment variables or configuration templates, not
committed credentials.

## Current Status

The public RAG implementation is included under `personaai/rag/`. Runtime
credentials, raw retrieval corpora, generated embeddings, and vector databases
are not included in this repository.
