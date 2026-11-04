# Single-cell secondary evaluation protocol

These protocol cards document the secondary MCP/local analysis. They are not
prospective registration or an execution log. The manuscript's primary
single-cell analyses were performed manually. See
[public analysis scope](../docs/reproducibility_scope.md).

## 1. Structure the question

Specify the tissue, gene, cell types, age groups, sex, and contrast. Distinguish
a descriptive association from a causal claim. CIRBP asks about hepatocyte
versus myeloid age-associated expression. PGAT asks about VEC/ASPC expression
and selected interaction scores; the proposed regenerative consequence requires
separate functional evidence.

## 2. Check feasibility

Verify input identity, genotype, gene/cell annotations, age groups, expression
scale and numbers of cells and animals. Nonempty groups are necessary but do
not establish statistical power. Record missing inputs or metadata rather than
substituting unrelated evidence. The inline report parser has liver/Cirbp case
defaults; review its specification before execution.

## 3. Execute the secondary workflow

MCP engines calculate expression summaries and pooled-cell CCI where relevant.
Local scanpy/scipy scripts calculate additional trends and cluster summaries.
Use the exact age grouping and scale documented in each case report. The
historical `log2fc_old_vs_young` column is a pseudocount-adjusted log2 ratio of
stored-scale means, not automatically a raw-count fold change. Individual cells
or age bins are not independent animals. The published mouse-level inference
must be distinguished from these descriptive checks.

## 4. Compare like quantities and disclose differences

`results/reproduction_check.json` is retained as a legacy filename. Labels are:

- `directionally-concordant` / `directionally-discordant`: signs agree/disagree
  around the declared reference point (0, or 1 for OR/ratios).
- `significance-category-agreement` / `significance-category-disagreement`:
  P values fall on the same/different side of 0.05; no claim of equal effects.
- `not-assessable`: missing/nonfinite values or no valid numerical reference
  or equivalence margin.

No label establishes numerical reproduction. Correlation versus log2 ratio,
different age contrasts, or different clusters must be named separately.
An age fraction exceeding 50% is not itself an enrichment test. PGAT's legacy
-1 and 0 targets are expectations, not measured effect sizes. Preserve
mismatches and original values; do not tune analyses to match a target or
attribute discrepancies to subsampling without testing that explanation.

## 5. Grade within scope

The current descriptive CIRBP helper requires valid positive young/old group
sizes for every candidate, finite observations, no feasibility blockers, and
an actual positive age contrast before assigning a support label. Expression
and induction must uniquely favor the same cell type; ties/conflicting origins
are mixed. This does not perform mouse-level significance or causal testing.
A sparse negative myeloid contrast does not exclude immune involvement.

The PGAT observations do not establish male specificity from a significant
male/nonsignificant female contrast, female equivalence, VEGFA–KDR interaction
activity, or an ASPC regenerative effect. Current reports retain those limits.

## 6. Report sources and interpretation

Provide the original tables, formulas, group definitions, input provenance,
and reference scope. Separate historical output labels from updated
interpretation and state when a documentation update was not a rerun. Cite
only the computations actually available. Case reports and
`aging_atlas_skill_cards/verification_report_authoring.md` implement this format.
