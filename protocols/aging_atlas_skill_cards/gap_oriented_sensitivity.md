# Gap-Oriented Sensitivity Card

## Purpose

This card defines how the verdict-driving metrics are independently recomputed
and cross-checked after the primary engine run.

## Common Gap Classes

- Composition distortion from equal-size subsampled atlas extracts.
- Leiden seed and package-version variation affecting OR and fold values.
- Proportion-axis estimates that differ from reference under subsampling.
- Significance not reached even when direction agrees.
- MCP engine internals being opaque to inspection.

## Decision Rules

1. Independently recompute each verdict-driving metric locally with plain
   scanpy/scipy (age trend, subcluster enrichment and stress markers,
   proportion trend, ligand/receptor change).
2. Compare three ways: MCP value, local recompute, and reference value.
3. Assign honest match labels: `reproduced`, `directional-only`, or `mismatch`.
4. Never force a match by tuning the seed or thresholds; record `mismatch`
   metrics as limitations.

## Application

For CIRBP, the local recompute reproduced the aged-enriched subcluster (aged
83.5%, OR > 1) and the senescence and ER-stress marker fold-changes, all labeled
`reproduced` despite absolute-value differences. For PGAT, the male molecular
signals reproduced, but the female VEC proportion trend was labeled `mismatch`
because the 30k equal-size subsample distorted composition; the verdict
therefore relied on the molecular axis and flagged a full-atlas recheck as the
remaining step.
