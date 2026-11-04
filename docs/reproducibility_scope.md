# Scope and provenance of the public analyses

Updated 2026-11-05. The repository contains recovered historical outputs and
executable analysis helpers. Updating the helpers does not mean that the
historical experiments were rerun.

| Material | Public location | What it supports |
|---|---|---|
| CRELD2 follow-up | `analysis/creld2_human_genetics/` | Lead-variant MR and regional coloc outputs, including palindromic-exclusion sensitivity |
| Complete five-candidate screen | `analysis/creld2_human_genetics/results/five_candidate_screen/` | Five targets by four outcomes; 19 estimates and one unavailable combination; original output hashes and drivers |
| Secondary CIRBP and PGAT checks | `analysis/cirbp_liver_single_cell/`, `analysis/pgat_aspc_single_cell/` | Extract-level descriptive results and directional comparison; not numerical reproduction of the manuscript models |
| Historical CIRBP reference | `analysis/cirbp_liver_single_cell/reference/` | The recovered, unchanged summary behind the historical targets |
| RAG implementation | `personaai/rag/` | Current code and configurable execution, not proof of historical model isolation |
| Protocol cards | `protocols/` | Documented workflow and interpretation rules; not a prospective registration or complete execution log |

## Primary manuscript analyses and secondary checks

The primary manuscript single-cell analyses were performed manually. The MCP
scripts here implement a separate secondary analysis. In that secondary
workflow, the MCP engine executes expression summaries and a local script adds
comparisons. They use related atlas data and are not independent biological
replications. Their observations, age contrasts, estimands, and clustering
settings differ from those in the primary analysis.

The final manuscript additionally reports mouse-level pseudobulk linear models,
quasi-binomial abundance models, period-by-sex tests, and senescence gene-set
comparisons. The exact scripts and analysis-ready per-mouse inputs that produced
those additional estimates have not been recovered in this repository. The
public secondary code must not be cited as reproducing those estimates. The
historical reference JSON does not fill that gap. Source data and methods in the
manuscript remain a separate source; no replacement historical script or run log
has been inferred from its reported results.

## Comparisons and retained records

`results/reproduction_check.json` is a legacy filename. Current `match` labels
state directional concordance/discordance, significance-category agreement/
disagreement, or inability to assess. None asserts numerical reproduction.
`legacy_match` preserves the previous label; original estimates are unchanged.
PGAT's -1/0 targets were qualitative placeholders, now separated from numeric
references. The original files are available at commit
`76ff056c5be751233a36f6d7ec196d2484fde5bc`; file hashes and transformations are
listed in [comparison_record_provenance.json](comparison_record_provenance.json).
The historical CIRBP P value stored as zero was rounded to five decimals; its
exact value is unavailable. New calculations retain floating-point precision.

## Historical RAG records

The manuscript reports Gemini 2.5 Pro. The prior public application default was
a different model and cannot establish which model served a historical run.
New runs must select `OPENROUTER_MODEL` explicitly. Corpus-only mode now disables
web fallback, Python execution, and arbitrary file-reading agent tools. This
controls application tools, not the model's parametric knowledge or a provider's
training data. It does not verify corpus dates automatically.

Past model snapshots, provider responses, seeds, complete loop histories,
web-access records, and human-intervention counts are not reconstructed here.
Current defaults cannot prove that web access was disabled in the past.
Likewise, completeness >= 0.90 is one search stopping condition, not a mandatory
scientific acceptance gate. See the [actual rubric and stop rules](table1_llm_scoring_rubric.md)
and [corpus provenance](../protocols/rag/corpus_provenance.md).

Figure 2 is interpreted as a retrospective comparison of generated questions
with later literature, rather than a time-locked, prospective prediction test.
The 2023 twelve-hallmark taxonomy was supplied during generation. Counts of 216
initial proposals, 157 specific questions after integration and subdivision,
and 114 retained questions describe different units; 216 to 157 was not simply
a deletion of 59 duplicate independent questions. These generation counts are
author-reported, not a reconstruction of all raw prompt-to-question mappings.

## Access and licensing

Raw atlas objects, QTL/GWAS inputs, retrieval corpora, embeddings, and credentials
are not bundled. Their absence is distinct from removal of unfavorable results;
negative results and sensitivity analyses remain public. A branch in this public
repository is also public. Root licensing does not override component-specific
notices retained in bundled packages; see each package's metadata and notices.
