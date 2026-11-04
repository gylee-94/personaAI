# RAG answer evaluation and stopping rules

This document describes `evaluate_answer_node()` in
`personaai/rag/backend/agent/nodes.py`. It replaces the earlier five-criterion
weighted screening table: that table was not the implemented evaluator, and
no saved CRELD2 score establishes passage through such a weighted gate.
The earlier document remains in Git history.

## Implemented evaluator

The same configured LLM used for generation evaluates the draft against the
query, main topics, and cited context. It returns `relevance`, `completeness`
(each 0 to 1), and `missing_info`. This is model self-assessment, not independent
human annotation, evidence validity, or a calibrated probability of truth.

| Field | Evaluation prompt |
|---|---|
| Relevance | Coverage, integration, accuracy, and precision in addressing the main topics |
| Completeness | Depth and analytical development of the topics and their relationships |
| Missing information | Specific gaps to guide another retrieval iteration |

The evaluator is instructed to use high scores conservatively and to clear
missing information only when its qualitative requirements and a completeness
score above 0.85 are met. The runtime does not enforce that instruction as an
acceptance threshold; its control flow uses the rules below.

## Actual stop conditions

| Condition | Consequence |
|---|---|
| Completeness >= 0.90 | Clear missing information and stop further retrieval |
| Completeness > 0.75, improvement < 0.05, loop count > 2 | Stop because improvement is limited |
| Loop count >= `MAX_SEARCH_ATTEMPTS` | Stop at the retrieval limit |
| Evaluator returns no missing information | Route to final output |
| Human selects accept at the review interruption | Use the current draft as final output |
| Retrieval/evaluation fails or retrieval exceeds its limit | Follow the error/fallback route; this is not scientific acceptance |

The first iteration with missing information routes to human review. Continuing
retrieval and accepting the draft are distinct decisions. These conditions do
not imply that every final hypothesis scored at least 0.90. The old
`COMPLETENESS_THRESHOLD` environment setting was unused and has been removed;
the implemented 0.90, 0.75, and 0.05 rules have been retained.

For new executions, graph state records evaluation scores, missing information
before/after the rules, stop reasons, and the number of completed human-review
decisions. Preserve the graph checkpoints or application logs to retain those
records. No historical iteration scores or human-intervention counts are
invented or recovered by this change.
