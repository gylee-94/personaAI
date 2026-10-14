# Five-candidate exploratory screen: recovered report

The archived report dated 22 May 2026 documents evaluation of FGF21, CRELD2,
GDF15, ADIPOQ and SERPINE1 against frailty index, DNAm GrimAge, leukocyte
telomere length and parental longevity. It records 19 estimated combinations;
ADIPOQ–parental longevity was not estimable because no harmonized overlapping
variants were available. This missing result is not a negative result.

## What is available

- `source_report_20260522.md`: historical Korean report, preserving numerical
  values and stage-by-stage execution status. One absolute local data-root path
  was replaced with a placeholder and trailing whitespace was normalized;
  `provenance.json` records both hashes.
- `all_candidate_outcomes.tsv`: all 20 candidate–outcome combinations, including
  the unavailable combination, reported beta/SE/nominal P, coloc SNP count and
  PP.H3/PP.H4. Confidence intervals are approximate, calculated as beta ± 1.96 SE
  from the **rounded report values**. They are not original full-precision output.
- `tissue_eqtl.tsv`: all 15 candidate–tissue entries; absent rows are identified.
- `pqtl_loci.tsv`: the five lead pQTL loci recorded in the report.

## Why CRELD2 was prioritized

All five targets had pQTL data. CRELD2–frailty was the only estimated combination
with PP.H4 > 0.5 (0.526), accompanied by lead-Wald nominal P = 0.00117 and tissue
cis-eQTL evidence in adipose and liver. No combination exceeded PP.H4 > 0.8.
Thus the report supports prioritization based on the observed exploratory
signals, not exclusion of the other four targets for low novelty or missing pQTL.
The report describes these thresholds; it does not establish preregistration.

Other nominal Wald associations were GDF15–telomere (P = 0.0283; PP.H4 = 0.0189)
and SERPINE1–parental longevity (P = 0.0240; PP.H4 = 0.0239). These results are
included rather than omitted. P values are unadjusted values from the source
report; neither these findings nor the CRELD2 prioritization are confirmatory.

GrimAge was examined in the historical screen and is disclosed here even though
it was not included in the adopted main Results. No additional exclusion reason
is established by the recovered report. Its exact GWAS accession and effect
units are not documented here; they must not be inferred from the trait name.

## Interpretation and units

The current public CRELD2 drivers read input BETA/SE values without phenotype
rescaling. The documented UKB-PPP source uses inverse-rank-normalized protein
levels (Sun et al., doi:10.1038/s41586-023-06592-6). The original outcome sources
use quantile-normalized FI (Atkins et al., doi:10.1111/acel.13459), log-transformed
Z-standardized LTL (Codd et al., doi:10.1038/s41588-021-00944-6), and Cox-model
Martingale residuals for combined parental attained age (Pilling et al.,
doi:10.18632/aging.101334). For those documented sources, MR units are outcome
scale units per unit inverse-rank-normalized protein. The recovered report does
not independently verify every original input transformation. GrimAge units
remain unspecified. Cross-outcome beta magnitudes are not directly comparable.

CRELD2 remains an exploratory follow-up candidate. The existing palindromic
exclusion result (frailty PP.H4 0.526 to 0.051) still applies. Different P values
across outcomes do not establish frailty specificity or a causal tissue-to-blood
mediation pathway.

## Reproduction boundary

This addition transcribes a historical report; **no new statistical analysis was
run**. The original all-candidate `run_hypothesis4_*` drivers, full-precision TSVs
and harmonized variant sets are named in the report but were not recovered with
it. The existing `run_creld2_*` drivers reproduce the documented CRELD2 workflow,
not the entire historical five-target screen.

From the repository root, regenerate and validate the transcribed tables:

```bash
python analysis/creld2_human_genetics/scripts/export_five_candidate_report.py
```

Validation checks the complete 5 × 4 coverage, the unavailable ADIPOQ combination,
and agreement of the three main CRELD2 outcomes with existing full-precision
MR and primary-coloc tables at the historical report's rounding precision.
For precise CRELD2 estimates, use the existing `../creld2_mr_lead_wald.tsv` and
`../creld2_coloc_abf.tsv`. The historical source is preserved as a record, not as
endorsement of every biological interpretation or proposed future method.
