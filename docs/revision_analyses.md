# Revision analyses for Figures 3 and 4

These author-supplied primary-analysis scripts, recorded logs, and three
per-mouse CSV tables were integrated on 2026-11-13. They implement the additional Figure 3 and
Figure 4 statistics reported in the revised manuscript and reviewer responses.
The scripts are retained unchanged under each case's `revision/` directory;
the repository runner and this guide adapt the supplied package for publication.
These analyses are separate from the older secondary MCP checks.

File provenance is recorded in [revision_source_manifest.tsv](revision_source_manifest.tsv).
The recorded logs are supplied outputs, not logs of a new full run during Git
integration. The dependency pins are the authors' supplied revision environment,
separate from the MCP environment. A complete installation and atlas rerun with
all those pins was not performed during repository integration.

## Layout

```
run_revision_analyses.sh
requirements-revision.txt
analysis/cirbp_liver_single_cell/revision/
  scripts/01_cirbp_mouse_level.py            Figure 3B
  scripts/02_c4_proportion_mouse_level.py    Figure 3D-G: C4 proportion, Leiden resolutions, Cirbp positivity, Table R3.4
  scripts/03_c4_senescence_gene_sets.py      Figure 3D-G: senescence gene sets
  results/                                   logs (*.log) and per-mouse source data (*.csv)
analysis/pgat_aspc_single_cell/revision/
  scripts/01_extract_gwat_from_atlas.py      gWAT cell metadata from the atlas (TileDB-SOMA)
  scripts/02_vec_proportion_mouse_level.py   Figure 4D: per-mouse VEC %, 12-month t-test, Spearman
  scripts/03_vec_proportion_quasibinomial.py Figure 4D: odds ratio per month, age x sex interaction
  scripts/04_midlife_contrasts.py            Figure 4D: 3-6 -> 12 months and 3-6 -> 16-23 months by sex
  scripts/05_vegfa_kdr_midlife.py            Additional expression models using Figure 4E-G source objects; no LIANA scores
  results/
```

## Reported values and where they come from

| Reported value | Script |
|---|---|
| Cirbp, hepatocytes, 3 vs 23 months, cell-level Wilcoxon P = 2.0 × 10⁻²² (523,330 and 159,675 cells) | cirbp `01` |
| Mean hepatocyte Cirbp higher in 8 of 10 mice at 23 months than in any of the 12 mice at 3 months | cirbp `01` |
| Per-mouse pseudobulk, hepatocytes: 0.036 log2 CPM per month, 95% CI 0.015–0.058, P = 0.001, n = 50 mice | cirbp `01` |
| Per-mouse pseudobulk, myeloid cells: 0.022, 95% CI −0.018 to 0.063, P = 0.28 | cirbp `01` |
| C4 among hepatocytes by age, pooled and per mouse (Table R1.5a); 3–93 hepatocytes per mouse | cirbp `02` (a) |
| C4 proportion at 23 vs 3–16 months: odds ratio 15.8, 95% CI 4.9–50.6, P < 0.001 | cirbp `02` (b) |
| C4 across Leiden resolutions 0.3–0.7 (Figure 3 legend) | cirbp `02` (c) |
| Cirbp detected in 15 of 2,372 hepatocytes (C1 5/1,123; C2 3/779; C3 1/295; C4 6/175); one or two UMIs per positive cell; Cdkn1a in 1.7% of C4 cells | cirbp `02` (d) |
| Dissociation-associated genes by cluster (Table R3.4) | cirbp `02` (e) |
| Fridman senescence-up P = 6 × 10⁻⁶; GO:BP cellular senescence P = 1 × 10⁻⁸ (Mann–Whitney) | cirbp `03` |
| 364,044 and 336,080 wild-type cells; 2, 4, 4, 2 and 4 mice per sex at 3, 6, 12, 16 and 23 months | pgat `01` |
| VEC % of every mouse (Table R1.6a); group means 19.9% vs 10.3% (males) and 24.9% vs 12.4% (females) at 3 vs 23 months | pgat `02` |
| 12 months, male vs female: unpaired t-test P = 0.039 | pgat `02` |
| Per-mouse Spearman: males ρ = −0.63, P = 0.009; females ρ = −0.51, P = 0.043 | pgat `02` |
| Odds ratio per month 0.969 (males, P = 0.002) and 0.970 (females, P = 0.015); interaction P = 0.90 | pgat `03` |
| 3–6 → 12 months: males 17.7% → 12.3% (−30%; OR 0.66, P = 0.040), females 19.4% → 22.5% (OR 1.27, P = 0.29); period × sex P = 0.033 | pgat `04` |
| 3–6 → 16–23 months: both sexes declined; period × sex P = 0.89 | pgat `04` |
| Kdr in ASPCs, 3–6 → 12 months: decline in males, not in females; period × sex P = 0.006. Vegfa in VECs: P = 0.067 | pgat `05` |

## Inputs (not redistributed)

The supplied package identifies the Mouse Aging Atlas (Zhang et al., Science
2025; [GEO GSE247719](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE247719))
as the source. The figure h5ads are processed author objects, not files available
under those exact names from GEO. An accession alone does not reconstruct their
selected cells, matrix transformations, or stored cluster labels. Exact objects
or a documented construction procedure are required for an independent full run.

| Variable | Contents |
|---|---|
| `PERSONAAI_FIGURE_DATA` | Folder with `Fig3_Cirbp_Liver/raw.data/liver_hepatocyte_myeloid_full.h5ad` (Figure 3B), `Fig3_Cirbp_Liver/raw.data/Cirbp_categorized_with_clusters.h5ad` (Figure 3D–G) and `Fig4_PGAT/raw.data/gWAT_{male,female}_30k.h5ad` (Figure 4E–G). These are the figure source objects. |
| `PERSONAAI_SOMA` | Folder with the atlas TileDB-SOMA experiments; `gWAT_experiment` is read (Figure 4D, all wild-type cells). |

Detailed input fields and matrix expectations are in the
[CIRBP input manifest](../analysis/cirbp_liver_single_cell/revision/input_manifest.tsv)
and [PGAT input manifest](../analysis/pgat_aspc_single_cell/revision/input_manifest.tsv).
The three included per-mouse CSVs are derived source data; they are not
replacements for the full expression or cluster objects in every analysis.

## What can be run from included tables

- `fig3b_per_mouse_pseudobulk.csv` contains the gene/library sums, ages and sexes
  needed for the Cirbp mouse-level models. The supplied CIRBP 01 script still
  reads the h5ad to create that table and also calculates cell-level summaries.
- `fig3dg_c4_per_mouse.csv` contains the C4 and total counts needed for the
  abundance model. CIRBP 02 also needs the h5ad for detection and cluster-label
  comparisons; CIRBP 03 needs its expression matrix for gene-set scoring.
- `gWAT_mouse_VEC_percent.csv` contains the per-mouse VEC and total counts.
  PGAT 03 runs directly on this included table. PGAT 02 and 04 read the metadata
  parquet generated by PGAT 01. The parquet is not versioned.
- PGAT 05 requires the two processed 30,000-cell figure h5ads. Its log contains
  expression-model summaries, not per-mouse expression inputs.

## Running

```bash
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -r requirements-revision.txt
export PERSONAAI_FIGURE_DATA=/path/to/figure_data PERSONAAI_SOMA=/path/to/soma_data
PYTHON=.venv/bin/python bash ./run_revision_analyses.sh
```

Run these commands from the repository root. The runner keeps the caller's
working directory, so relative Python and input paths remain valid. It checks
the required input paths before running analyses and stops if any script fails.
It rewrites the corresponding logs and generated tables under `revision/results/`;
use a clean working copy to compare a new run with the supplied outputs.

For a table-only example, after installing dependencies:

```bash
.venv/bin/python analysis/pgat_aspc_single_cell/revision/scripts/03_vec_proportion_quasibinomial.py
```

The full-run duration depends on the environment and input access. No measured
compute/human-time breakdown is inferred from the supplied logs.
`analysis/pgat_aspc_single_cell/revision/intermediate/` holds the cell-metadata
parquet written by PGAT 01. It is git-ignored and recreated on each full run.

## Scope not supplied by this package

This package does not include the original atlas-to-figure sampling and
clustering construction pipeline, the per-age raw-UMI LIANA driver underlying
Figure 4G, the Supplementary Figure 4 differential-expression driver, or all
original figure-plotting scripts. Historical LIANA output CSVs remain available
under the PGAT `reference/` directory. The older `scripts/run_mcp_cci.py` pools
different ages and conditionally normalizes/log1p-transforms X; it is not an
exact substitute for the manuscript's stated raw-count per-age calculation.

## Definitions

- **Pseudobulk CPM.** For each mouse and cell type: sum of the gene's UMI counts divided by the sum of the cells' UMI counts, × 10⁶. Models use log2(CPM + 1).
- **Quasi-binomial models.** Binomial GLM on per-mouse counts (cells of the type, other cells) with dispersion set to Pearson χ²/df.
- **Age** is in months (3, 6, 12, 16, 23).
- **P values** are two-sided.
