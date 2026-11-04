# PGAT ASPC Single-Cell Workflow

This directory contains a secondary analysis of VEC/ASPC expression and selected
ligand–receptor scores in aging gWAT. It does not directly measure regeneration
or establish a causal, male-specific VEGFA–KDR mechanism.

## Analysis scope

This is a secondary MCP/local check, separate from the manual manuscript
analysis. It provides descriptive expression/cluster/interaction outputs and
directional comparisons, not exact reproduction of the manuscript's mouse-level
models. See [the report](results/pgat_aspc_verification_report.md) and
[public scope](../../docs/reproducibility_scope.md).

## Required External Data

See `data_manifest.tsv`. The Mouse Aging Atlas gWAT experiment, the atlas-derived
sex-split h5ads are not redistributed. Recovered historical LIANA reference CSVs
are included under `reference/` with hashes.

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
