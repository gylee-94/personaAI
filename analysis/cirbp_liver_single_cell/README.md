# CIRBP Liver Single-Cell Workflow

This directory contains a secondary workflow for examining cell-associated patterns of
age-related liver CIRBP (*Cirbp*) upregulation using Mouse Aging Atlas
single-cell RNA-seq data.

## Analysis scope

This is a secondary MCP/local check, separate from the manual manuscript
analysis. It provides descriptive expression/cluster/interaction outputs and
directional comparisons, not exact reproduction of the manuscript's mouse-level
models. See [the report](results/cirbp_liver_verification_report.md) and
[public scope](../../docs/reproducibility_scope.md).

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

Recorded statistical outputs are retained. The comparison filename
`reproduction_check.json` is historical: its current labels describe only
direction/significance categories. Original labels are preserved separately.
The current report specifies contrasts, expression scales, reference
provenance, disagreements, and untested mechanisms. Updating code/documentation
on 2026-11-05 did not rerun the atlas analysis.

## Related Protocol Documents

The analysis should be read together with the public protocol provenance files:

- `../../protocols/aging_atlas_evaluation_protocol.md`
- `../../protocols/protocol_library_manifest.tsv`
- `../../docs/agent_assistance_disclosure.md`
