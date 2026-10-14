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
  from the **rounded report values**. They are not original full-precision output;
  full-precision values are in `original_outputs/`.
- `tissue_eqtl.tsv`: all 15 candidate–tissue entries; absent rows are identified.
- `pqtl_loci.tsv`: the five lead pQTL loci recorded in the report.
- `original_outputs/`: the full-precision outputs of the original run, copied
  byte-for-byte: `hypothesis4_mr_lead_wald.tsv`, `hypothesis4_coloc_abf_r.tsv`,
  `hypothesis4_followup_summary.tsv` and `pqtl_locus_manifest.tsv`. The 20
  harmonized variant sets are not redistributed; `harmonized_inputs_manifest.tsv`
  records their row counts, sizes and SHA-256 hashes.
- `../../scripts/hypothesis4_original/`: the original drivers that produced those
  outputs (`run_hypothesis4_pqtl_followup.py`, `run_hypothesis4_coloc_r.R`). The
  Python driver is unchanged; in the R driver two absolute local paths were
  replaced with placeholders. `provenance.json` records original and archived
  hashes.

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
is established by the recovered report. The GrimAge outcome was GWAS Catalog
GCST90014288 (DNAm GrimAge acceleration, European-ancestry meta-analysis;
McCartney et al., doi:10.1186/s13059-021-02398-9). The local raw file matches the
Catalog md5 `05111c5f4764ea883847ffa83eacf5ab`. Its units are given below.

## Interpretation and units

The current public CRELD2 drivers read input BETA/SE values without phenotype
rescaling. The documented UKB-PPP source uses inverse-rank-normalized protein
levels (Sun et al., doi:10.1038/s41586-023-06592-6). The original outcome sources
use quantile-normalized FI (Atkins et al., doi:10.1111/acel.13459), log-transformed
Z-standardized LTL (Codd et al., doi:10.1038/s41588-021-00944-6), and Cox-model
Martingale residuals for combined parental attained age (Pilling et al.,
doi:10.18632/aging.101334). For those documented sources, MR units are outcome
scale units per unit inverse-rank-normalized protein. The recovered report does
not independently verify every original input transformation.

GrimAge acceleration is the age-adjusted `AgeAccelGrim` output of the Horvath
epigenetic age calculator, analysed in linear models adjusted for sex and genetic
principal components and meta-analysed with METAL (McCartney et al.). No
standardization step is described in the source, which reports Mendelian
randomization effects on GrimAge acceleration in years. The summary statistics
are consistent with that scale: the median implied phenotype SD,
SE·√(2·EAF·(1−EAF)·N) over variants with 0.1 < EAF < 0.9, is 3.72, against 0.98,
0.98 and 0.99 for the frailty, telomere and parental-longevity inputs. The local
conversion copied Effect/SE unchanged. GrimAge MR estimates are therefore years
of GrimAge acceleration per unit inverse-rank-normalized protein. The summary
statistics file itself carries no unit label; this rests on the source
publication and the implied SD. Cross-outcome beta magnitudes are not directly
comparable.

The original coloc driver sets `sdY = 1` for every outcome. This matches the
frailty, telomere and parental-longevity inputs (implied SD ≈ 1; pQTL exposures
0.83–0.97), so the CRELD2 main results are unaffected. For GrimAge (SD ≈ 3.7
years) it makes the effect-size prior about 3.7-fold narrower than intended on
the trait scale. The GrimAge PP values (all PP.H4 < 0.08) were computed under
that prior and have not been rerun.

CRELD2 remains an exploratory follow-up candidate. The existing palindromic
exclusion result (frailty PP.H4 0.526 to 0.051) still applies. Different P values
across outcomes do not establish frailty specificity or a causal tissue-to-blood
mediation pathway.

## Reproduction boundary

**No new statistical analysis was run** for this disclosure. The original
all-candidate drivers and full-precision outputs were recovered from the local
analysis directory in which the report was written; that report's SHA-256 equals
`original_file_sha256`. File timestamps place the drivers (23:13), outputs
(23:14–23:24) and report (23:30 KST, 22 May 2026) in that order. The directory
was not under version control, so hashes and timestamps are the only provenance
evidence. Rerunning the drivers requires the raw UKB-PPP archives and GWAS files
named in the report, which are not redistributed; the Python driver resolves its
data root as the parent of its own directory. The existing `run_creld2_*` drivers
remain the maintained route for the CRELD2 workflow.

From the repository root, regenerate and validate the transcribed tables:

```bash
python analysis/creld2_human_genetics/scripts/export_five_candidate_report.py
```

Validation checks the complete 5 × 4 coverage, the unavailable ADIPOQ combination,
agreement of all 19 estimated combinations with `original_outputs/` (MR beta, SE
and P; coloc SNP count, PP.H3 and PP.H4), and agreement of the three main CRELD2
outcomes with the existing full-precision MR and primary-coloc tables, all at the
historical report's rounding precision. For precise estimates, use
`original_outputs/` for all candidates or the existing `../creld2_mr_lead_wald.tsv`
and `../creld2_coloc_abf.tsv` for CRELD2. The historical source is preserved as a record, not as
endorsement of every biological interpretation or proposed future method.
