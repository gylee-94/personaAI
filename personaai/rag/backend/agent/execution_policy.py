"""Explicit retrieval boundary and observable stopping decisions.

These settings govern new executions; they do not reconstruct historical runs.
This module has no model, network, or vector-store dependencies.
"""
import os
import uuid


def new_run_audit(environ=None):
    """Start a fresh per-request record; checkpoints retain preceding requests."""
    environ = os.environ if environ is None else environ
    return {
        "audit_run_id": str(uuid.uuid4()),
        "evaluation_history": [],
        "human_decision_count": 0,
        "stop_reason": None,
        "previous_completeness": 0.0,
        "execution_config": {
            "configured_model": environ.get("OPENROUTER_MODEL"),
            "temperature": environ.get("LLM_TEMPERATURE", "0.0"),
            "corpus_only": corpus_only_mode(environ),
            "configured_collection": environ.get("QDRANT_COLLECTION"),
            "max_search_attempts": int(environ.get("MAX_SEARCH_ATTEMPTS", 5)),
        },
    }


def corpus_only_mode(environ=None):
    environ = os.environ if environ is None else environ
    value = environ.get("RAG_CORPUS_ONLY", "true").strip().lower()
    if value not in {"true", "false", "1", "0"}:
        raise ValueError("RAG_CORPUS_ONLY must be true/false or 1/0")
    return value in {"true", "1"}


def make_web_tool(factory, environ=None):
    environ = os.environ if environ is None else environ
    if corpus_only_mode(environ):
        return None
    api_key = environ.get("TAVILY_API_KEY")
    if not api_key:
        raise ValueError("General mode requires TAVILY_API_KEY; use RAG_CORPUS_ONLY=true for corpus retrieval only")
    return factory(api_key=api_key)


def make_agent_tools(citation_tool, code_tool, file_tools_factory, web_factory, environ=None):
    """Do not expose Python/network or arbitrary local-file tools in corpus mode."""
    if corpus_only_mode(environ):
        return [citation_tool]
    return [code_tool, make_web_tool(web_factory, environ), citation_tool, *file_tools_factory()]


def evaluation_stop_reasons(completeness, previous_completeness, loop_count, max_attempts, missing_info):
    """Describe the existing stop rules, without treating them as scientific acceptance."""
    reasons = []
    if completeness >= 0.90:
        reasons.append("completeness_at_least_0.90")
    if completeness - previous_completeness < 0.05 and completeness > 0.75 and loop_count > 2:
        reasons.append("limited_improvement")
    if loop_count >= max_attempts:
        reasons.append("maximum_search_attempts")
    if not missing_info:
        reasons.append("evaluator_no_missing_information")
    return reasons
