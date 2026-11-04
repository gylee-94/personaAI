# Methods for the secondary PGAT check

This document describes the public MCP/local pipeline, separate from the
manually performed manuscript analysis and additional mouse-level models.

The MCP runner summarizes Vegfa expression in WT, sex-split 30,000-cell gWAT
extracts and compares 3 versus 23 months. Its log2 contrast is
`log2((old_mean + 0.01)/(young_mean + 0.01))` on the stored X scale. The local
script instead averages age-bin means equally across <=6-month and >=16-month
groups, subtracts young from old for VEC Vegfa and ASPC Kdr, and computes
Spearman correlation of age-bin VEC proportions with age. These are different
estimands and do not treat mice as the statistical unit.

The secondary CCI driver pools 3+6 versus 16+23-month cells per sex and uses
LIANA with a 10% expression filter and `use_raw=False`. It normalizes/log1p
when X maximum exceeds 50. The saved Lpl–Lrp1, Sparc–Fgfr1 and Pdgfb–Lrp1 scores
do not test VEGFA–KDR. This also differs from the manuscript's separate age
runs on raw UMI counts. Score changes have no mouse-level confidence interval.

Comparison labels indicate direction or significance categories only. The
historical male -1/female 0 expression targets were expectations, not effect
estimates; female equivalence cannot be assessed without a defined margin.
Both subsets have negative age-bin VEC trends. The reason for disagreement
with the historical female target is unverified. No statistical rerun occurred
in the 2026-11-05 update. The results neither directly measure ASPC regeneration
nor establish causal signaling or a sex interaction.
