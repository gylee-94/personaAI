# Verification Report Authoring Card

## Purpose

This card defines how the single-cell verification report is composed from the
analysis outputs, so that the way the verdict is produced is documented and
reproducible. The report is the human-readable artifact that turns the MCP-first
hybrid run plus the local cross-check into an adjudicated verdict over the
competing hypotheses. A report authored from this card is structurally identical
to one produced directly by the single-cell evaluation skill.

## Report Structure

The report uses the following fixed sections, in order. Every section maps to a
concrete analysis output under `results/`.

1. **Overall verdict** — the competing-hypothesis conclusion, followed by a
   verdict-basis table (one row per hypothesis / prediction: verdict + key
   reason).
2. **Data availability** — hybrid framing: the MCP engines are the primary
   execution and the local recompute is the cross-check verification. Lists
   tissue, gene(s), candidate cell types, age / sex / genotype metadata, input
   h5ads, and per-group cell counts.
3. **Cell-type expression (MCP)** — cell-type expression profile from the MCP
   `cell_type_expression.tsv`.
4. **Age dynamics (MCP)** — age trajectory and young-old contrast from the MCP
   `age_trajectory.tsv` / `young_old_contrast.tsv`.
5. **Subcluster / CCI** — aged-enriched subcluster phenotype, or VEC->ASPC-style
   ligand-receptor strength comparison, depending on `analysis_intent`.
6. **Stage-by-stage (5-stage, MCP-first) table** — one row per stage
   (Feasibility, Extraction / Spec, SC analysis / report, CCI, Cross-check,
   Verdict) with what ran, tool / output, and verdict.
6b. **Reproduction check (3-way)** — a transparency table that places, per
   verdict-driving metric, the **MCP value | local recompute | reference target |
   match** columns side by side, reporting `local` / `mcp` / `target` / `match`
   verbatim from `reproduction_check.json`. The match label is one of
   `reproduced` / `directional-only` / `mismatch`.
7. **Interpretation** — competing hypotheses read separately (Hypothesis A
   supported vs Hypothesis B rejected), each tied to the converging evidence
   lines.
8. **Conclusion** — a causal-chain diagram followed by an explicit limitations
   block.
9. **Outputs** — driver and output paths, reference provenance, figures.

## Authoring Rules

- **Every number is cited from `results/*`** and must be grep-reproducible from
  the named TSV / JSON; no figure is asserted that cannot be traced to an output
  file.
- **Honest match labels** in section 6b: `reproduced` (sign / rank / significance
  direction agrees), `directional-only` (direction agrees, exact value or
  significance falls short), `mismatch` (direction disagrees). Labels are never
  forced by seed or threshold tuning.
- **`mismatch` is disclosed as a limitation in section 8, never hidden**, with
  its cause stated (e.g. subsample composition distortion). A mismatched metric
  does not anchor the verdict.
- **Repo-relative paths only** — no absolute or machine-specific paths in the
  report.
- **The LLM drafts the verdict prose; the deterministic results and cross-check
  supply the numbers.** Interpretation is authored, the quantities are read from
  the output files.
- OR / fold values are interpreted directionally because Leiden seed and
  package-version variation make their absolute values irreproducible.

## Application

The CIRBP liver report
(`analysis/cirbp_liver_single_cell/results/cirbp_liver_verification_report.md`)
and the PGAT ASPC report
(`analysis/pgat_aspc_single_cell/results/pgat_aspc_verification_report.md`) were
authored from this card. The CIRBP report flagged all eight cross-check metrics
`reproduced`; the PGAT report retained the female VEC proportion `mismatch` as an
explicit section-8 limitation and rested the verdict on the reproduced
male-specific molecular signal instead.
