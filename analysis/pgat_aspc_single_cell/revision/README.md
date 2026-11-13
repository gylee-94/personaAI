# Primary PGAT revision analyses

The author-supplied scripts and recorded outputs in this directory cover
Figure 4D VEC abundance, age/period-by-sex models, and the additional mouse-level
Vegfa/Kdr pseudobulk analysis. They are separate from the secondary MCP and
LIANA workflow in the parent directory.

See the [revision guide](../../../docs/revision_analyses.md) for dependencies,
input paths, reported values, and execution. Input requirements are listed in
[input_manifest.tsv](input_manifest.tsv). The supplied code and results are
tracked by [SHA-256](../../../docs/revision_source_manifest.tsv).

`03_vec_proportion_quasibinomial.py` can run directly on the included per-mouse
VEC-count CSV. Scripts 02 and 04 use the cell metadata extracted by 01 from the
external atlas store. Script 05 reads the two external figure h5ads and fits
gene-expression models; it does not generate LIANA interaction scores or the
Supplementary Figure 4 differential-expression results.
