# PGAT ASPC Single-Cell Workflow

This directory contains the public workflow for testing whether the age-related
decline of adipocyte stem and progenitor cells (ASPC) in gonadal white adipose
tissue (gWAT) is driven, male-specifically, by deterioration of the vascular
endothelial cell (VEC) niche and loss of the VEGF-VEGFR axis, using Mouse Aging
Atlas single-cell RNA-seq data.

## Analysis Summary

The workflow tests two competing, non-mutually-exclusive hypotheses for the
age-related ASPC decline:

- Hypothesis A (VEC niche / VEGF axis, male-specific)
- Hypothesis B (sex-non-specific / preserved)

It integrates:

- a bundled single-cell analysis engine (MCP) run once per sex under a
  lineage-screening intent, producing cell-type expression, sex-stratified age
  trajectory, young-old contrast, and an evidence-grading verdict
- a cell-cell interaction (CCI) component (LIANA backend) comparing VEC->ASPC
  ligand-receptor signalling young vs old per sex, for the target pairs
  Lpl-Lrp1, Sparc-Fgfr1, Pdgfb-Lrp1
- a deterministic local cross-check (plain scanpy/scipy) that recomputes the key
  decision metrics per sex (VEC proportion trend, VEC *Vegfa* old-young, ASPC
  *Kdr* old-young)
- a three-way comparison [local | mcp | target] recorded in
  `results/reproduction_check.json`

The adopted verdict is **VEC-niche / VEGF-axis-supported (male-specific)**
(Hypothesis A), carried by the reproduced male molecular signal. An honest caveat
on the cell-proportion axis is described under Interpretation and Limitations.

## Required External Data

See `data_manifest.tsv`. The Mouse Aging Atlas gWAT experiment, the atlas-derived
sex-split h5ads, and the reference LIANA CSVs are not redistributed in this
repository.

Expected local layout when reproducing the scripts:

```text
<aging-atlas-home>/
  gWAT_male_30k.h5ad             # male sex-split 30k subset
  gWAT_female_30k.h5ad           # female sex-split 30k subset
  liana/
    male_VEC_ASPC_interactions.csv     # CCI reference direction (provenance)
    female_VEC_ASPC_interactions.csv   # CCI reference direction (provenance)
```

The bundled MCP / CCI engines are expected at `personaai/scrna_mcp` (overridable
via the `PERSONAAI_MCP_HOME` environment variable). The cross-check imports
`sc_analysis_mcp.h5ad_compat` from there and falls back to `scanpy.read_h5ad` if
that module is unavailable.

## Reproduction

Run the deterministic cross-check (regenerates
`results/reproduction_check.json`):

```bash
python analysis/pgat_aspc_single_cell/scripts/crosscheck.py \
  --aging-atlas-home /path/to/atlas
```

Drive the bundled MCP engine to regenerate the per-sex cell-type / trajectory /
contrast / grading tables (requires `personaai/scrna_mcp` and the atlas h5ads):

```bash
python analysis/pgat_aspc_single_cell/scripts/run_mcp_report.py \
  --aging-atlas-home /path/to/atlas \
  --h5ad gWAT_male_30k.h5ad \
  --out analysis/pgat_aspc_single_cell/results/male
```

Run the CCI component (requires the CCI engine and its LIANA virtual
environment):

```bash
python analysis/pgat_aspc_single_cell/scripts/run_mcp_cci.py \
  --aging-atlas-home /path/to/atlas \
  --out analysis/pgat_aspc_single_cell/results/cci
```

## Interpretation

The tracked results reproduce the main finding for males: the VEGF axis is
downregulated with age in the gWAT VEC niche. Male VEC *Vegfa* falls strongly
(young-old log2fc = -2.701; 3.39% -> 0.17% expressing) versus female -0.153, and
male ASPC *Kdr* (VEGFR2) declines (old-young = -0.0295) versus female +0.0013.
All three male VEC->ASPC target pairs weaken in old (Lpl-Lrp1 1.547 -> 1.150,
Sparc-Fgfr1 1.018 -> 0.886, Pdgfb-Lrp1 0.990 -> 0.928), agreeing with the male
reference LIANA direction; the female reference shows none of the three pairs
weakened. The verdict is therefore **male-specific support** for the VEC-niche /
VEGF-axis hypothesis on the molecular axis.

Honest caveat (cell-proportion axis): the deterministic cross-check finds that
the **female VEC proportion also declines** (Spearman rho = -0.7), contradicting
the "female stable" reference (+0.1); this is recorded as `mismatch` in
`results/reproduction_check.json`. It is attributed to equal-bin 30k subsampling
distorting composition, and a full-atlas composition re-check is needed. The
verdict rests on the molecular signal (*Vegfa*/*Kdr*/CCI), not the proportion
axis. The analysis is associational rather than causal.

## Related Protocol Documents

The analysis should be read together with the public protocol provenance files:

- `../../protocols/aging_atlas_evaluation_protocol.md`
- `../../protocols/protocol_library_manifest.tsv`
- `../../docs/agent_assistance_disclosure.md`
