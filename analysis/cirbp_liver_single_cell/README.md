# CIRBP Liver Single-Cell Workflow

This directory contains the public workflow for resolving the cell of origin of
age-related liver CIRBP (*Cirbp*) upregulation using Mouse Aging Atlas
single-cell RNA-seq data.

## Analysis Summary

The workflow tests two competing, non-mutually-exclusive hypotheses for the
age-related liver *Cirbp* increase:

- Hypothesis A (hepatocyte-intrinsic stress origin)
- Hypothesis B (Kupffer/myeloid immune origin)

It integrates:

- a bundled single-cell analysis engine (MCP) run under a lineage-screening
  intent, producing cell-type expression, sex-stratified age trajectory,
  young-old contrast, and an evidence-grading verdict
- a deterministic local cross-check (plain scanpy/scipy) that recomputes the key
  decision metrics, identifies an aged-enriched hepatocyte subcluster, and scores
  senescence / ER-stress markers
- a three-way comparison [local | mcp | target] recorded in
  `results/reproduction_check.json`

The adopted verdict is **hepatocyte-supported** (Hypothesis A).

## Required External Data

See `data_manifest.tsv`. The Mouse Aging Atlas Liver experiment and the
atlas-derived liver h5ads are not redistributed in this repository.

Expected local layout when reproducing the scripts:

```text
<aging-atlas-home>/
  liver_hepatocyte_myeloid_full.h5ad         # lineage age trend
  liver_hepatocyte_myeloid_comparison.h5ad   # subcluster + stress markers
```

The bundled MCP engine is expected at `personaai/scrna_mcp` (overridable via the
`PERSONAAI_MCP_HOME` environment variable). The cross-check imports
`sc_analysis_mcp.h5ad_compat` from there and falls back to `scanpy.read_h5ad` if
that module is unavailable.

## Reproduction

Run the deterministic cross-check (regenerates
`results/reproduction_check.json`):

```bash
python analysis/cirbp_liver_single_cell/scripts/crosscheck.py \
  --aging-atlas-home /path/to/atlas
```

Drive the bundled MCP engine to regenerate the cell-type / trajectory / contrast
/ grading tables (requires `personaai/scrna_mcp` and the atlas h5ad):

```bash
python analysis/cirbp_liver_single_cell/scripts/run_mcp_report.py \
  --aging-atlas-home /path/to/atlas \
  --h5ad liver_hepatocyte_myeloid_comparison.h5ad \
  --out analysis/cirbp_liver_single_cell/results/mcp
```

## Interpretation

The tracked results reproduce the main finding: liver *Cirbp* age-related
upregulation is hepatocyte-supported (Hypothesis A). Hepatocytes show dominant
baseline expression (0.973% vs 0.578% expressing) and the only positive age
induction (log2fc old/young = +1.556 vs myeloid -2.419). The deterministic
cross-check identifies an aged-enriched hepatocyte subcluster (83.54% aged,
OR 8.273) carrying senescence and stress signatures (*Cdkn1a* 7.811x, *Cirbp*
3.748x, *Xbp1* 2.599x, *Atf4* 1.046x). The analysis is associational rather than
causal, and absolute odds ratios / fold-changes are interpreted directionally
because they depend on Leiden seed and package versions.

## Related Protocol Documents

The analysis should be read together with the public protocol provenance files:

- `../../protocols/aging_atlas_evaluation_protocol.md`
- `../../protocols/protocol_library_manifest.tsv`
- `../../docs/agent_assistance_disclosure.md`
