# PersonaAI Paper Reproducibility Repository

This repository contains public, reproducible materials for PersonaAI-assisted
in-silico hypothesis evaluation. The current release includes the CRELD2 human
genetics workflow used to evaluate whether tissue secretory-stress candidates
nominated from the adipose-liver aging axis are supported by population-scale
genetic evidence. It also includes a single-cell aging-atlas workflow (CIRBP
liver cell-of-origin and PGAT sex-specific vascular endothelial niche) evaluated
against the Mouse Aging Atlas.

The language-model assisted component was used for workflow organization,
candidate evaluation, retrieval-assisted context assembly, and documentation.
Human-genetics estimates and single-cell outputs are provided with Python/R
scripts. Author-supplied scripts, logs, and per-mouse tables for the manuscript's
additional Figure 3 and Figure 4 analyses are now available in each single-cell
case's `revision/` directory. These are separate from the existing secondary
MCP checks. See [revision analyses and inputs](docs/revision_analyses.md) and
[public analysis scope](docs/reproducibility_scope.md).

## Contents

```text
analysis/creld2_human_genetics/
  README.md
  data_manifest.tsv
  methods_draft.md
  scripts/
    run_creld2_pqtl_followup.py
    run_creld2_coloc_abf.R
    plot_creld2_summary.py
    hypothesis4_original/   # recovered original all-candidate drivers
  results/
    pqtl_locus_manifest.tsv
    creld2_mr_lead_wald.tsv
    creld2_coloc_abf.tsv
    five_candidate_screen/  # archived report, transcribed tables + original_outputs/

analysis/cirbp_liver_single_cell/   (README, data_manifest, methods_draft, scripts/, results/)
analysis/pgat_aspc_single_cell/     (README, data_manifest, methods_draft, scripts/, results/ + CCI)

analysis/cirbp_liver_single_cell/revision/  (primary revision scripts, logs, per-mouse CSVs)
analysis/pgat_aspc_single_cell/revision/    (primary revision scripts, logs, per-mouse CSV)
run_revision_analyses.sh
requirements-revision.txt

protocols/
  human_genetics_evaluation_protocol.md
  protocol_library_manifest.tsv
  human_genetics_skill_cards/
  aging_atlas_evaluation_protocol.md
  aging_atlas_skill_cards/

docs/
  agent_assistance_disclosure.md
  contribution_guide.md
  table1_llm_scoring_rubric.md
  supplementary_table6_human_genetics_workflow.tsv

personaai/rag/
  README.md
  backend/
  run_full_indexing.py
  langgraph.json

personaai/scrna_mcp/
  aging_atlas_mcp/   (engine source)
  sc_analysis_mcp/   (engine source)
  cci_analysis_mcp/  (engine source)

protocols/rag/
  rag_protocol.md
  retrieval_corpus_manifest.tsv
  prompt_and_tool_disclosure.md
```

The [five-candidate screening disclosure](analysis/creld2_human_genetics/results/five_candidate_screen/README.md)
provides the recovered historical report, all reported candidate–outcome
results, and the original full-precision outputs and drivers. Its transcription
and reproduction limits are documented separately.

Raw GTEx, UKB-PPP, and GWAS summary statistics are not redistributed. The data manifest lists the required external resources and expected local filenames.

## Scope

This repository documents the MR and colocalization workflow for CRELD2 and the
single-cell aging-atlas workflow, and includes the public RAG implementation
under `personaai/rag/`. RAG corpora, embedding
databases, private prompts, API keys, and local runtime configuration are
intentionally excluded from version control.

The single-cell directories include primary revision statistics as well as
secondary descriptive and directional-check outputs, public protocol provenance,
and MCP engine source. Raw and processed single-cell objects (h5ad/SOMA), runtime
venvs, private prompts, and credentials remain excluded from version control.
The revision input manifest distinguishes public atlas data from the specific
processed figure objects needed by the scripts; an atlas accession alone does
not reconstruct those objects or their exact sampled cells and cluster labels.

## Protocol Provenance

The public protocol documents translate the internal agent-assisted workflow
into reviewable analysis logic. They document hypothesis structuring,
feasibility assessment, statistical genetics execution, gap-oriented
sensitivity review, and evidence grading. These documents describe analysis logic; they are not prospective registration
or complete historical execution logs. Executable scripts support the specific
outputs identified in each case report.

## Workflow

Each evaluation follows the same protocol-driven stages, defined in
`protocols/<domain>_evaluation_protocol.md` and registered in
`protocols/protocol_library_manifest.tsv`. Every stage maps to a skill card
under `protocols/<domain>_skill_cards/` (`<domain>` is `human_genetics` or
`aging_atlas`):

| Stage | Skill card | Output |
|---|---|---|
| 1. Hypothesis structuring | `hypothesis_structuring.md` | testable hypothesis specification |
| 2. Feasibility assessment | `feasibility_assessment.md` | data-availability / go–no-go |
| 3. Execution | `single_cell_execution.md` (MCP engines under `personaai/scrna_mcp/`) or `statistical_genetics_execution.md` (deterministic MR / coloc scripts) | `analysis/<case>/results/*.tsv` |
| 4. Gap-oriented sensitivity / cross-check | `gap_oriented_sensitivity.md` | `reproduction_check.json` (secondary direction/significance check) or sensitivity analyses |
| 5. Evidence grading | `evidence_grading.md` | verdict call |
| 6. Verification report authoring | `verification_report_authoring.md` | `analysis/<case>/results/<case>_verification_report.md` |

The human-readable verdict (the verification report) is authored per
`verification_report_authoring.md`: it follows a fixed section structure and
cites only numbers already present in the deterministic `results/` files, so the
report is reviewable and reproducible. Worked examples:
`analysis/cirbp_liver_single_cell/results/cirbp_liver_verification_report.md`,
`analysis/pgat_aspc_single_cell/results/pgat_aspc_verification_report.md`, and
`analysis/creld2_human_genetics/results/creld2_verification_report.md`.

## RAG Contribution Boundary

RAG code lives under `personaai/rag/`. Public protocol descriptions belong under
`protocols/rag/`. Do not commit raw retrieval corpora, vector stores, generated
embeddings, private prompts, local credentials, or local path configuration. Use
`protocols/rag/retrieval_corpus_manifest.tsv` to document corpus provenance and
access requirements.

## Reproducibility Note

Requirements depend on the workflow. The primary revision statistics run as
Python scripts without an LLM runtime; they require the specified figure source
objects or atlas store and the dependencies in `requirements-revision.txt`.
RAG and secondary MCP workflows have separate runtime requirements. This
repository ships code, protocols, and recorded outputs; it does not reconstruct
all primary figures from a fresh atlas download. See the
[revision running instructions](docs/revision_analyses.md#running).

## License

See the root `LICENSE` (MIT; Copyright 2026 BioNexus). Bundled components retain
their own notices and package metadata; the root license does not override
component-specific restrictions.

## Current records and corrections

- [Complete five-candidate genetics screen](analysis/creld2_human_genetics/results/five_candidate_screen/README.md), including negative/unavailable outcomes and original output hashes.
- [Analysis scope and historical limitations](docs/reproducibility_scope.md).
- [Implemented RAG evaluation and stop rules](docs/table1_llm_scoring_rubric.md).
- [Corpus count units and provenance](protocols/rag/corpus_provenance.md).

New RAG runs require an explicit model and default to corpus-only tool access.
This does not retrospectively establish historical model isolation. Secondary
single-cell comparison labels now distinguish direction from numerical
reproduction. Original estimates and sensitivity results are preserved.

Offline regression checks (numpy/pandas required):

```bash
python -m unittest discover -s tests -v
```
