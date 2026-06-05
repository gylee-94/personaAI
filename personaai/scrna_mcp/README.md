# scRNA MCP Engines

This directory vendors the three Model Context Protocol (MCP) server engines that
power PersonaAI's single-cell RNA-seq analyses. Each engine is an independent,
self-contained MCP server exposing a set of tools that an LLM agent (or any MCP
client such as Claude Desktop) can call over stdio.

## Engines

### 1. `aging_atlas_mcp/` — TileDB-SOMA extraction
A [FastMCP](https://github.com/jlowin/fastmcp) server that reads the Mouse Aging
Atlas single-cell data stored as TileDB-SOMA experiments and extracts subsets as
AnnData / `.h5ad` for downstream analysis.

Tools (`src/aging_atlas_mcp/server.py`):
- `soma_list_experiments` — list available tissue experiments
- `soma_open_experiment` — open and summarize one experiment
- `soma_explore_cell_types` — inspect cell-type composition of an experiment
- `soma_to_anndata_for_screening` — quick in-memory AnnData subset for screening
- `soma_to_h5ad_for_analysis` — export a filtered subset to an `.h5ad` file

### 2. `sc_analysis_mcp/` — scanpy preprocessing / clustering / DE
A scanpy-based MCP server covering the standard single-cell workflow: loading,
QC, normalization, HVG selection, PCA/UMAP, Harmony integration, Leiden
clustering, visualization, marker/DE detection, and aging-specific contrasts. It
also ships `scrna_report_runner.py`, a higher-level driver that turns a stated
hypothesis into a graded, plotted scRNA evidence report.

Tools (`sc_analysis_mcp/server.py`, 34 total) include:
- Loading / status: `sc_check_status`, `sc_load_h5ad`, `sc_load_10x`, `sc_load_10x_multi`
- Preprocessing: `sc_quality_control`, `sc_normalize`, `sc_find_hvg`,
  `sc_subset_clusters`, `sc_subset_cells`
- Dimensionality reduction / integration: `sc_compute_pca`, `sc_compute_umap`,
  `sc_harmony_integrate`, `sc_check_batch_effect`
- Clustering: `sc_leiden_clustering`, `sc_rename_clusters`
- Plotting: `sc_plot_umap`, `sc_plot_cell_proportions`, `sc_plot_violin`,
  `sc_plot_dotplot`, `sc_plot_heatmap`, `sc_plot_volcano`, `sc_plot_ma`,
  `sc_plot_deg_heatmap`, `sc_plot_deg_dotplot`
- Differential expression: `sc_find_markers`, `sc_get_deg_results`,
  `sc_export_deg`, `sc_compare_groups`, `sc_find_markers_vs_rest`,
  `sc_pseudobulk_deg`
- Aging / specialized: `sc_gene_trajectory`, `sc_gene_correlation`,
  `sc_expression_variance`, `sc_aging_deg`, `sc_sex_dimorphism`

`scrna_report_runner.py` — CLI/library driver that resolves an Aging-Atlas
dataset for a hypothesis, runs preflight feasibility checks, summarizes
cell-type expression / age trajectory / young-vs-old contrast, grades the
evidence, and renders a report with figures.

### 3. `cci_analysis_mcp/` — LIANA cell-cell interaction
An MCP server that runs ligand-receptor cell-cell interaction (CCI) analysis with
[LIANA+](https://liana-py.readthedocs.io/).

Tools (`cci_analysis_mcp/server.py`):
- `cci_run_analysis` — run LIANA `rank_aggregate` on an `.h5ad`
- `cci_compare_aging` — compare CCI between young vs old (sex-stratified)
- `cci_query_interactions` — query specific L-R pairs or cell-type pairs
- `cci_plot_dotplot` — dotplot of interactions
- `cci_plot_network` — network/chord visualization of interactions

## Environment

- **`SOMA_BASE_PATH`** — location of the Aging Atlas TileDB-SOMA experiments used
  by `aging_atlas_mcp`. Defaults to `./soma_data`; override via env var.
- **`CCI_DATA_DIR`** — location of CCI input data for `cci_analysis_mcp`.
  Defaults to `./cci_data`; override via env var.
- **Python dependencies** — each engine declares its own deps:
  - `aging_atlas_mcp`: `requirements.txt` / `setup.py` (Python ≥3.8;
    fastmcp, tiledbsoma, pandas)
  - `sc_analysis_mcp`: `pyproject.toml` (Python ≥3.11; scanpy, anndata,
    harmonypy, …), installable via `pip install -e .`
  - `cci_analysis_mcp`: runs in an **isolated environment** because LIANA pins
    conflicting versions. A `uv.lock` is provided — rebuild with
    [`uv`](https://docs.astral.sh/uv/): `uv sync`. This environment provides
    `liana`.

## Usage with the analysis pipelines

These are the same engines invoked by the single-cell analyses under
`analysis/*_single_cell/scripts/run_mcp_*.py`, which locate the engines through
the `PERSONAAI_MCP_HOME` environment variable (pointing at this
`personaai/scrna_mcp/` directory).

## Boundary statement

This repository vendors **engine source only**. Not included:
- runtime virtual environments (`.venv/`, build artifacts)
- raw single-cell objects (`.h5ad` files, TileDB-SOMA stores)
- private prompts and any credentials

Users must supply their own atlas data and compute. Data paths are env-driven
with neutral relative defaults; no machine-specific paths or secrets are
embedded.

## License

MIT.
