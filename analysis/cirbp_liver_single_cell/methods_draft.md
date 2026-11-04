# Methods for the secondary CIRBP check

This document describes the public MCP/local pipeline, not the manually
performed primary manuscript analysis or its mouse-level models.

The MCP runner summarizes stored expression by candidate cell type, age and
sex, and compares 3- versus 23-month cells. Its `log2fc_old_vs_young` is
`log2((old_mean + 0.01)/(young_mean + 0.01))`, not a raw-count fold change. The
trajectory summary pools candidate cell types within each sex/age bin. The
current descriptive grade requires complete candidate coverage, nonempty age
groups, finite values and a positive contrast; it does not test significance.

The local script calculates cell-level Spearman correlation in hepatocytes. A
separate multi-gene input is clustered using up to 4,000 cells, seed 0, 2,000
HVGs, 30 PCs and Leiden resolution 1.0. The cluster with the largest OR for
16+23-month enrichment is selected. Marker values are ratios of mean X plus
1e-9 (cluster/rest). The loader normalizes/log1p-transforms X when its maximum
exceeds 30; this heuristic is not proof of the original scale.

The historical reference uses 2,372 hepatocytes and a 23-month contrast with
different clustering settings. Its source JSON is included under `reference/`.
The comparison JSON retains the old filename but reports direction/category
agreement only. Original results were not recalculated for the 2026-11-05
documentation update. Sparse expression, cluster selection and shared atlas
inputs limit inference; myeloid contributions and causal mechanisms are not
excluded by this secondary check.
