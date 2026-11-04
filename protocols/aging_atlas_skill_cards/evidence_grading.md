# Descriptive evidence grading card

The automatic CIRBP helper summarizes a cell-origin pattern, not causal
validation or mouse-level significance. It requires all specified candidates,
finite expression/contrasts, observed young and old cells, and no feasibility
blockers. Only a positive age contrast can support induction. A unique shared
leader in mean expression and positive contrast can receive
`hepatocyte-supported` or `immune-supported`; ties/disagreement are `mixed`,
nonpositive contrasts `weak`, and incomplete evidence `insufficient` or
`partial-celltype-comparison`.

The underlying formula uses stored expression means and does not test power,
sex effects, or biological replication. The inline parser has CIRBP/liver
defaults; it is not a general biological validator.

The archived CIRBP label is compatible with its positive hepatocyte contrast,
but a sparse negative myeloid contrast does not reject immune involvement.
PGAT results are descriptive expression/score associations. Male-specificity
requires interaction inference, female equivalence requires an explicit test,
and ASPC regeneration and VEGFA–KDR activity were not directly measured here.
