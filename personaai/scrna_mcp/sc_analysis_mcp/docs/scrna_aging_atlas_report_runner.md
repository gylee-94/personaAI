# scRNA-seq Aging Atlas Report Runner Design

## Goal

Build a deterministic scRNA-seq report runner that mirrors the human genetics
skill-card skeleton while using Aging Atlas single-cell data and reusable
`sc_analysis_mcp` analysis functions. The runner accepts inline hypothesis text,
extracts a small structured analysis spec, executes fixed Aging Atlas analyses,
and writes TSV, JSON, PNG, and Markdown report outputs.

## Relationship to Human Genetics Cards

The human genetics workflow uses this five-step skeleton:

1. Hypothesis structuring
2. Feasibility assessment
3. Statistical genetics execution
4. Sensitivity review
5. Evidence grading

The scRNA-seq runner keeps the same reasoning skeleton but changes the evidence
layer:

1. **scRNA hypothesis structuring**
   - Extract tissue, gene, candidate cell origins, age contrast, and biological
     alternatives from inline hypothesis text.
   - Example: Liver/CIRBP with hepatocyte-stress versus immune-cell activation
     alternatives.
2. **Aging Atlas feasibility assessment**
   - Resolve the fixed Aging Atlas h5ad dataset for the tissue.
   - Confirm that the requested gene and metadata columns exist.
   - Resolve gene names across exact, case-fold, symbol-column, and raw
     AnnData universes.
   - Resolve candidate cell-type labels through exact, normalized, and
     Aging Atlas alias matches.
   - Check candidate cell-type counts and young/old group availability.
3. **scRNA-seq execution**
   - Load h5ad with `read_h5ad_compat`.
   - Reuse `sc_analysis_mcp` aging functions for report plots when possible.
   - Generate structured TSV/JSON outputs for cell-type expression, age
     trajectory, young-old contrast, and figure metadata.
4. **Sensitivity review**
   - Report genotype filtering, sex stratification, candidate cell-type counts,
     missing metadata, low expression, and annotation limitations.
5. **Evidence grading**
   - Grade whether the observed single-cell signal supports a hepatocyte-driven,
     immune/myeloid-driven, mixed, weak, or unsupported cellular origin.

## Why Use Wrapper Functions Instead of Live MCP Server Calls

The runner imports and reuses `sc_analysis_mcp` Python functions directly rather
than depending on a live MCP server session. This preserves the genetics
workflow principle that analysis can be reproduced by running deterministic
scripts. The MCP server remains useful for interactive exploration, but report
generation should not depend on server runtime state.

## Dataset Resolution Scope

The MVP is fixed to Mouse Aging Atlas liver data, but it does not use a single
default h5ad for every CIRBP task. The runner selects an h5ad from the parsed
inline hypothesis spec and analysis intent.

```text
Aging_Agent/Figure_data/Fig3_Cirbp_Liver/raw.data/
  liver_hepatocyte_myeloid_comparison.h5ad  # lineage screening
  liver_hepatocyte_myeloid_full.h5ad        # full-scale lineage screening
  aging_atlas_clustered.h5ad                # hepatocyte deep-dive / clustering
```

For the manuscript-style CIRBP question, the inline hypothesis contains Liver,
CIRBP, hepatocyte stress, and Kupffer/myeloid immune activation. This maps to
`analysis_intent=lineage_screening`, so the resolver prefers the comparison h5ad
that contains both `Hepatocytes` and `Myeloid cells`. The clustered h5ad is used
for later hepatocyte-intrinsic subcluster analysis, not for the initial
hepatocyte-versus-myeloid adjudication.

## Aging Atlas Inventory And Preflight Contract

Because this runner is intentionally fixed to Aging Atlas rather than arbitrary
GEO inputs, the expected defense is dataset inventory rather than late runtime
guessing. The runner provides:

```bash
python -m sc_analysis_mcp.scrna_report_runner \
  --inventory-root Aging_Agent/Figure_data \
  --inventory-out-dir Aging_Agent/sc_rnaseq_reports/inventory
```

This writes:

```text
aging_atlas_h5ad_inventory.json
aging_atlas_h5ad_inventory.tsv
```

Each h5ad inventory row records:

- shape, obs columns, var columns, raw presence, raw gene count
- obs column value summaries for bounded categorical columns
- AnnData X dtype, sampled maximum value, inferred data state
- obs index dtype, so downstream code can avoid label-index misuse

The report runner then calls `preflight_aging_atlas()` before execution. The
preflight result is written to `feasibility.json` and includes:

- `gene_resolution`: query gene, resolved native gene, match kind, symbol-column
  and raw-recovery flags
- `cell_type_resolution`: exact/normalized/alias/miss result for each requested
  candidate cell origin
- `blockers`: missing h5ad schema, missing gene, missing cell type, or missing
  age groups
- `warnings`: case-fold gene resolution, raw-only gene recovery, or alias-based
  cell-type resolution

Analysis code consumes the resolved native gene and matched cell-type labels.
Expression vectors are indexed only by positional indices or boolean masks, not
by AnnData `obs.index` labels. This prevents barcode-string index failures.

## Output Layout

The default output directory is:

```text
Aging_Agent/sc_rnaseq_reports/<hypothesis_id>/
```

Each run writes:

```text
hypothesis.md
spec.json
feasibility.json
results/
  cell_type_expression.tsv
  age_trajectory.tsv
  young_old_contrast.tsv
  evidence_grading.tsv
figures/
  F1_cell_type_expression.png
  F2_age_trajectory_by_sex.png
  F3_young_old_contrast.png
  F4_mcp_gene_trajectory.png
  F5_mcp_expression_variance.png
  F6_mcp_sex_dimorphism.png
figure_manifest.tsv
report.md
```

## Plot Handling

The runner handles plots in two layers:

1. **Standard report plots**
   - Built from structured calculations for stable captions and report
     integration.
   - Examples: cell-type expression, age trajectory, young-old contrast.
2. **MCP-derived plots**
   - Generated by `sc_gene_trajectory`, `sc_expression_variance`, and
     `sc_sex_dimorphism`.
   - Stored in the same figures directory and referenced through
     `figure_manifest.tsv`.

## CIRBP Liver Interpretation Contract

For the CIRBP liver hypothesis, the runner compares:

- Hypothesis A: hepatocyte stress origin
- Hypothesis B: immune/myeloid activation origin

Evidence is graded as:

- **Hepatocyte-supported:** hepatocytes show dominant expression and stronger
  old-versus-young induction than myeloid cells.
- **Immune-supported:** myeloid/Kupffer-like cells show dominant expression or
  stronger age induction.
- **Mixed:** both candidate origins show meaningful expression or induction.
- **Weak/insufficient:** gene expression is too sparse, cell counts are too low,
  or age groups are unavailable.

## Non-Goals

- This MVP does not perform live MCP server orchestration.
- This MVP does not download new data.
- This MVP does not generalize to every tissue automatically.
- This MVP does not create PPTX output.
- This MVP does not make causal claims from scRNA-seq evidence alone.
