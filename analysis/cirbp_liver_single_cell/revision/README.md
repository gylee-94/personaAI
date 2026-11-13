# Primary CIRBP revision analyses

The author-supplied scripts and recorded outputs in this directory cover
Figure 3B Cirbp pseudobulk models, Figure 3D–G C4 abundance and detection
summaries, and cell-level senescence gene-set comparisons. They are separate
from the secondary MCP workflow in the parent directory.

See the [revision guide](../../../docs/revision_analyses.md) for dependencies,
input paths, reported values, and execution. Input requirements are listed in
[input_manifest.tsv](input_manifest.tsv). The supplied code and results are
tracked by [SHA-256](../../../docs/revision_source_manifest.tsv).

The scripts retain the cells and genotype composition of the supplied figure
objects; they do not add a WT-only filter. Cluster and alternative Leiden labels
are read from the existing object rather than recomputed. The gene-set test
uses cells, whereas the pseudobulk and abundance models use mice.
