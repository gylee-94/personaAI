# Verification Report Authoring Card

## Purpose

This card defines how the human-genetics verdict report is composed from the
analysis outputs, so that the way the verdict is produced is documented and
reproducible. The report turns the deterministic MR / colocalization scripts and
the gap-oriented sensitivity checks into an adjudicated, honestly graded verdict
over the candidate. A report authored from this card is structurally identical to
one produced directly by the statistical-genetics evaluation skill.

## Report Structure

The report uses the following fixed sections, in order. Every section maps to a
deterministic result TSV.

1. **Overall verdict** — the candidate-level conclusion (exploratory support vs
   non-support), followed by a verdict-basis table (one row per target /
   outcome: verdict + key reason).
2. **Data availability** — eQTL / pQTL / GWAS availability: tissue cis-eQTL
   evidence, circulating pQTL availability, and the aging GWAS outcomes, with
   local source files and significance.
3. **pQTL locus manifest** — lead variant, locus window, lead significance, and
   locus variant count per target.
4. **Lead-pQTL Wald MR** — single-lead-variant Wald ratio MR per target /
   outcome (beta, SE, P), interpreted as directional evidence only.
5. **Colocalization** — regional `coloc.abf()` results per target / outcome with
   **PP.H3** and **PP.H4**, applying the predefined thresholds (PP.H4 > 0.8
   strong, PP.H4 > 0.5 moderate).
6. **Stage-by-stage table** — one row per analysis stage (instrument selection,
   tissue / TWAS evidence, MR, coloc / SMR, downstream annotation) with the
   original analysis and the current execution / verdict.
7. **Target / interpretation** — each candidate read separately, tying eQTL,
   pQTL, MR, and coloc into a per-target interpretation.
8. **Conclusion + limitations** — a causal-chain summary for the leading
   candidate followed by an explicit limitations block (single-instrument MR,
   potential cohort overlap, missing downstream data).
9. **Outputs** — script and result-TSV paths, harmonized variant sets, reference
   provenance.

> NOTE: the human-genetics report has **no 3-way MCP / local / reference table**.
> That construct is specific to the single-cell hybrid (MCP primary + local
> cross-check) and must not be invented here. Human-genetics verification instead
> rests on deterministic scripts plus targeted sensitivity analyses (e.g. allele
> harmonization checks, palindromic-variant exclusion).

## Authoring Rules

- **Every number is cited from a deterministic result TSV** (locus manifest, MR
  lead-Wald, coloc abf) and must be grep-reproducible from the named file; no
  estimate is asserted that cannot be traced to a script output.
- **Exploratory vs confirmatory grading** is explicit: lead-variant Wald MR is
  directional evidence; `PP.H4 > 0.8` is strong and `PP.H4 > 0.5` is moderate
  colocalization support. Discordant MR and coloc results are reported without
  forcing a causal conclusion.
- **Limitations are explicit** in section 8: single-instrument MR, potential
  UK Biobank exposure-outcome overlap, palindromic / strand-ambiguity handling,
  and the need for independent non-UKB replication for confirmatory claims.
- **Repo-relative paths only** — no absolute or machine-specific paths in the
  report.
- **The LLM drafts the verdict prose; the deterministic scripts supply the
  numbers.** Interpretation is authored, the estimates are read from the result
  TSVs.

## Application

The CRELD2 human-genetics analysis (`analysis/creld2_human_genetics/` —
`methods_draft.md` plus the `results/pqtl_locus_manifest.tsv`,
`results/creld2_mr_lead_wald.tsv`, and `results/creld2_coloc_abf.tsv` result
files) follows this card. CRELD2 was reported as exploratory genetic support for
frailty-related aging biology — directionally consistent lead-Wald MR and
moderate frailty colocalization — rather than as a definitive causal claim, with
single-instrument MR and potential cohort overlap retained as explicit
limitations.
