# Scope and provenance of the public analyses

Updated 2026-11-13. The repository contains recovered historical outputs and
executable analysis helpers. Updating the helpers does not mean that the
historical experiments were rerun.

| Material | Public location | What it supports |
|---|---|---|
| CRELD2 follow-up | `analysis/creld2_human_genetics/` | Lead-variant MR and regional coloc outputs, including palindromic-exclusion sensitivity |
| Complete five-candidate screen | `analysis/creld2_human_genetics/results/five_candidate_screen/` | Five targets by four outcomes; 19 estimates and one unavailable combination; original output hashes and drivers |
| Primary Figure 3 revision analyses | `analysis/cirbp_liver_single_cell/revision/` | Supplied Cirbp pseudobulk, C4 abundance and gene-set scripts, logs, and per-mouse tables |
| Primary Figure 4 revision analyses | `analysis/pgat_aspc_single_cell/revision/` | Supplied VEC abundance, period-by-sex and Vegfa/Kdr pseudobulk scripts, logs, and VEC per-mouse counts |
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

The author-supplied revision package was integrated on 2026-11-13. It covers
mouse-level pseudobulk linear models, quasi-binomial abundance models,
period-by-sex tests, and cell-level senescence gene-set comparisons. The
`revision/` directories retain the supplied analysis code, result logs, and three
per-mouse CSV tables. Their SHA-256 hashes are recorded in
[revision_source_manifest.tsv](revision_source_manifest.tsv). Adding these
files does not mean the complete analysis was rerun during repository integration.

The required processed figure h5ads and the atlas SOMA store are not bundled.
The [revision guide](revision_analyses.md) identifies each input, which analyses
can use the included per-mouse tables, and the remaining data-preparation scope.
The supplied scripts read existing sampled cells and cluster labels; they do
not recreate every figure object from a fresh atlas download. The original
per-age raw-UMI LIANA driver for Figure 4G and the Supplementary Figure 4
differential-expression driver are also outside this supplied package. Existing
reference CSVs are outputs, not substitutes for those drivers.

The older MCP checks remain separate secondary analyses. In particular, the
PGAT secondary CCI driver differs from the manuscript analysis in both age
grouping and expression preprocessing (conditional normalization/log1p versus
the manuscript's stated raw UMI counts). Direction differences cannot be assigned
to pooling alone. The new Vegfa/Kdr pseudobulk script does not regenerate the
LIANA interaction scores. No historical estimate has been replaced by a new
value inferred from manuscript text.

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
