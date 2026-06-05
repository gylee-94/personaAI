# Feasibility Assessment Card

## Purpose

This card defines whether a candidate hypothesis has sufficient compatible
single-cell evidence in the Mouse Aging Atlas for downstream analysis.

## Evidence Checks

- Experiment availability in the TileDB-SOMA store for the target tissue.
- Presence of the candidate gene or genes in the variable annotation.
- Age, sex, and genotype metadata sufficient to define young and old groups.
- Enough cells per candidate cell type and per group for stable estimates.
- Consistent cell-type annotation and data normalization state.

## Decision Rules

1. Proceed only with components that can be mapped to available atlas layers.
2. Do not infer missing layers from unrelated proxy data.
3. Record limitations when annotation, subsampling, or group sizes affect
   interpretation.
4. Flag composition distortion from subsampled extracts as a feasibility caveat
   rather than correcting it silently.

## Application

For CIRBP, the liver comparison extract carried Cirbp with WT genotype across
five age groups and both sexes, with hepatocytes and myeloid cells annotated as
candidate cell types. For PGAT, the male and female gWAT extracts each carried
Vegfa and Kdr with VEC and ASPC annotated as candidates; both were feasible, but
the 30k equal-size subsampling was recorded as a composition caveat for the
proportion axis.
