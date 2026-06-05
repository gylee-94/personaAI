# Single-Cell Execution Card

## Purpose

This card maps a feasible single-cell hypothesis to deterministic analysis
engine modules.

## Analysis Modules

- SOMA-to-h5ad extraction for the target tissue, genes, and groups.
- Cell-type expression profiling across candidate cell types.
- Age trajectory across age groups, with sex stratification when required.
- Young-old differential contrast (log2 fold change and percent expressing).
- Subclustering to identify aged-enriched populations and stress signatures.
- LIANA-based ligand-receptor cell-cell interaction comparison (young vs old)
  for niche or communication hypotheses.

## Decision Rules

1. MCP engines run the primary analysis; language-model assistance only
   organizes the workflow and drafts the verdict.
2. Run sex-stratified hypotheses once per sex on single-sex extracts.
3. Include the cell-cell interaction module only for niche or communication
   hypotheses; skip it for lineage-screening, subcluster, trajectory, and
   enrichment hypotheses.
4. Interpret expression and interaction estimates as supportive of cellular
   context, not causal inference.

## Application

The CIRBP analysis ran lineage screening (cell-type expression, age trajectory,
young-old contrast) on the liver extract; the aged-enriched stress subcluster
was characterized in the local cross-check. The PGAT analysis ran the same
single-cell modules per sex on the gWAT extracts and added the LIANA cell-cell
interaction module to compare VEC-to-ASPC ligand-receptor pairs between young
and old.
