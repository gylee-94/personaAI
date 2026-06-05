# Evidence Grading Card

## Purpose

This card defines how the workflow interprets competing hypotheses and grades
single-cell evidence.

## Interpretation Rules

- Single-cell association is supportive of cellular origin or context, not
  causal.
- OR and fold values are interpreted directionally because Leiden seed and
  package-version variation make their absolute values irreproducible.
- Converging expression, age-dynamic, subcluster, and interaction evidence
  raises confidence in the supported hypothesis.
- Metrics labeled `mismatch` in the cross-check are reported as limitations and
  do not anchor the verdict.
- The competing hypothesis is rejected only when the single-cell prediction it
  makes is contradicted in direction.

## Application

CIRBP was graded `hepatocyte-supported`: hepatocytes showed dominant expression,
positive aging induction (log2fc +1.556), and an aged-enriched stress subcluster
with senescence and ER-stress markers, while myeloid cells moved in the opposite
direction (log2fc -2.419), rejecting the immune-origin hypothesis. PGAT was
graded `VEC-niche / VEGF-axis-supported (male-specific)`: male VEC Vegfa loss,
male ASPC Kdr decline, and weakened male VEC-to-ASPC ligand-receptor signaling
reproduced and were conserved in females, with the female VEC proportion
mismatch retained as an explicit caveat.
