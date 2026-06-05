# CRELD2 Human Genetics Verification Report: Circulating CRELD2 and Aging-Related Outcomes

> hypothesis_id: `creld2_human_genetics`
> Hypothesis under test: Is genetically predicted circulating CRELD2 — a
> secretory stress-related candidate nominated from the adipose-liver aging axis
> — associated with aging-related outcomes (frailty index, leukocyte telomere
> length, parental longevity)?
> Execution mode: protocol-driven human-genetics evaluation — deterministic
> Python / R statistical-genetics scripts (lead-pQTL Wald-ratio MR + Bayesian
> colocalization) with gap-oriented palindromic sensitivity analysis. The
> language model structures and grades the verdict; every estimate is read from
> the deterministic result TSVs.

## 1. Overall Verdict

The final verdict of this analysis is a **frailty-specific, moderate
exploratory candidate signal — not confirmatory**. Among the three aging
outcomes tested, only frailty shows a coherent picture: the single-lead-variant
Wald-ratio MR is directionally positive and nominally significant (mr_beta
0.0360, SE 0.0111, z 3.245, p = 1.17e-3), and regional `coloc.abf()` returns a
moderate posterior for a shared causal variant (PP.H4 = 0.526, above the
predefined moderate threshold of 0.5 but below the strong threshold of 0.8).
Telomere length (MR p = 0.692) and parental longevity (MR p = 0.568) show no
directional MR signal and negligible colocalization (PP.H4 = 0.0011 and 0.0044
respectively). The frailty colocalization is sensitive to the lead variant:
because rs74510325 is a C/G palindromic SNP, excluding palindromic variants
drops frailty PP.H4 from 0.526 to 0.051. The CRELD2-frailty link is therefore
reported as an exploratory candidate to pursue, not as a definitive causal
claim.

| Outcome | MR signal | Coloc (PP.H4 / PP.H3) | Call |
|---|---|---|---|
| Frailty index | Directional, nominal p = 1.17e-3 (z = 3.245) | 0.526 / 0.026 (moderate) | **Exploratory support** (palindromic-sensitive) |
| Leukocyte telomere length | None (p = 0.692) | 0.0011 / 0.721 (distinct signals) | Not supported |
| Parental longevity | None (p = 0.568) | 0.0044 / 0.081 | Not supported |

---

## 2. Data Availability

Per `data_manifest.tsv`; raw resources are not redistributed in this repository.

- **Tissue cis-eQTL** — GTEx v8 cis-eQTL evidence for CRELD2 in Adipose
  Subcutaneous, Adipose Visceral Omentum, and Liver (GTEx Portal egenes files).
- **Circulating pQTL** — UK Biobank Pharma Proteomics Project (UKB-PPP) plasma
  CRELD2 pQTL summary statistics
  (`CRELD2_Q6UXH1_OID20751_v1_Inflammation`; raw archive not redistributed).
- **Aging GWAS outcomes** (GRCh37-aligned summary statistics):
  - Frailty index — Atkins et al. (`GCST90020053_frailty_index`)
  - Leukocyte telomere length — Codd et al. (`ieu-b-4879_telomere_length`)
  - Parental longevity — Pilling et al.
    (`GCST006697_parental_longevity_combined_attained_age`)
- **Reference allele frequency** — gnomAD, used for orientation of the
  palindromic lead SNP rs74510325.

The pQTL summary statistics were harmonized with each aging GWAS at the variant
level. Because the aging GWAS were aligned to GRCh37, pQTL-GWAS matching used
GRCh37 positions, and alleles were aligned to the pQTL effect allele before
downstream MR and colocalization.

---

## 3. pQTL Locus Manifest

Source: `results/pqtl_locus_manifest.tsv`

| target | lead SNP | rsID | chrom | lead −log10P | locus window | locus variants |
|---|---|---|---:|---:|---|---:|
| CRELD2 | `22:50315382:C:G:imp:v1` | rs74510325 | 22 | 354.247 | chr22:49,815,382–50,815,382 | 7,157 |

The strongest CRELD2 cis-pQTL signal (lead −log10P = 354.247) defines a ±500 kb
cis-locus (chr22:49,815,382–50,815,382) containing 7,157 locus variants, used
for the downstream lead-Wald MR and regional colocalization.

---

## 4. Lead-pQTL Wald-Ratio MR

Source: `results/creld2_mr_lead_wald.tsv`
(method = `lead_locus_pqtl_wald`, instrument = lead pQTL `22:50315382:C:G:imp:v1`
/ rs74510325, pQTL −log10P = 354.247)

| outcome | mr_beta | mr_se | mr_z | mr_p |
|---|---:|---:|---:|---:|
| frailty | 0.0360 | 0.0111 | 3.245 | **1.17e-3** |
| telomere | -0.0027 | 0.0069 | -0.396 | 0.692 |
| parental_longevity | 0.0043 | 0.0075 | 0.571 | 0.568 |

This is a single-lead-variant Wald-ratio MR, interpreted as **directional
evidence only** — it is not an LD-clumped multi-instrument IVW estimate and is
not definitive causal inference. Only the frailty estimate is directionally
positive and nominally significant (p = 1.17e-3); telomere and parental
longevity are null.

---

## 5. Colocalization

Source: `results/creld2_coloc_abf.tsv` (regional `coloc.abf()`; predefined
thresholds: PP.H4 > 0.8 strong, PP.H4 > 0.5 moderate)

### 5.1 Primary analysis

| outcome | nsnps | PP.H3 | PP.H4 | Interpretation |
|---|---:|---:|---:|---|
| frailty | 3,595 | 0.026 | **0.526** | Moderate shared-causal-variant support (>0.5, <0.8) |
| telomere | 6,125 | 0.721 | 0.0011 | High PP.H3 → distinct signals, not shared |
| parental_longevity | 5,237 | 0.081 | 0.0044 | No shared signal |

Only frailty reaches moderate colocalization support (PP.H4 = 0.526). For
telomere, PP.H3 = 0.721 indicates the pQTL and GWAS signals are present but
driven by distinct causal variants; parental longevity shows neither.

### 5.2 Sensitivity: palindromic-variant exclusion

| outcome | analysis | nsnps | PP.H3 | PP.H4 |
|---|---|---:|---:|---:|
| frailty | primary | 3,595 | 0.026 | 0.526 |
| frailty | exclude_palindromic | 3,117 | 0.045 | **0.051** |

The CRELD2 lead pQTL rs74510325 is a **C/G palindromic SNP**. Repeating the
colocalization after excluding palindromic variants drops frailty PP.H4 from
0.526 to 0.051 (n = 3,117). The frailty colocalization support is therefore
**sensitive to the inclusion of the palindromic lead variant**. The variant was
retained in the primary analysis because its minor allele frequency was
consistent across the pQTL dataset, frailty GWAS, and gnomAD, and was
sufficiently distant from 0.5 to resolve strand ambiguity; the sensitivity
result is reported transparently rather than forcing a causal conclusion.

---

## 6. Stage-by-Stage Verification Table

| Stage | What ran | Tool / output | Verdict |
|---|---|---|---|
| 1. Hypothesis structuring | Frame CRELD2 (adipose-liver secretory stress candidate) against three aging outcomes (frailty / telomere / parental longevity) | `methods_draft.md` | Pass (candidate + outcomes defined) |
| 2. Feasibility | Confirm GTEx v8 eQTL, UKB-PPP pQTL, and GRCh37 aging GWAS availability | `data_manifest.tsv` | Pass (all resources available; raw not redistributed) |
| 3. Statistical-genetics execution | pQTL locus extraction (±500 kb), pQTL-GWAS harmonization to pQTL effect allele, lead-Wald MR, regional `coloc.abf()` | `scripts/run_creld2_pqtl_followup.py`, `scripts/run_creld2_coloc_abf.R` → `results/pqtl_locus_manifest.tsv`, `creld2_mr_lead_wald.tsv`, `creld2_coloc_abf.tsv` | Pass (lead locus, MR, and coloc computed for all three outcomes) |
| 4. Gap-oriented sensitivity | Palindromic-SNP orientation check (gnomAD AF) + colocalization re-run excluding palindromic variants | `scripts/run_creld2_coloc_abf.R` → `creld2_coloc_abf.tsv` (`exclude_palindromic` row) | Pass (frailty PP.H4 sensitivity quantified: 0.526 → 0.051) |
| 5. Evidence grading | Apply MR directionality + PP.H4 thresholds (0.5 moderate / 0.8 strong); grade per outcome | this report | Pass — **frailty: moderate exploratory; telomere / parental: not supported** |

---

## 7. Interpretation

### 7.1 Frailty (exploratory support)
Two lines of evidence converge for frailty. The lead-pQTL Wald-ratio MR is
directionally positive and nominally significant (mr_beta 0.0360, p = 1.17e-3),
and regional colocalization returns a moderate posterior for a shared causal
variant (PP.H4 = 0.526, PP.H3 = 0.026). This convergence supports an
exploratory CRELD2–frailty link. The support is tempered, however, by the
palindromic sensitivity analysis: because rs74510325 is a C/G palindromic SNP,
excluding palindromic variants collapses frailty PP.H4 to 0.051. The signal is
therefore an exploratory candidate to follow up, not a confirmed causal effect.

### 7.2 Telomere length and parental longevity (not supported)
Neither outcome is supported. Telomere MR (p = 0.692) and parental-longevity MR
(p = 0.568) are null, and both have negligible PP.H4 (0.0011 and 0.0044). For
telomere, the high PP.H3 (0.721) indicates the CRELD2 pQTL and the
telomere-length GWAS each carry signal at the locus but from **distinct causal
variants**, so a shared-variant interpretation is rejected.

---

## 8. Conclusion

```text
CRELD2 cis-pQTL (lead rs74510325, −log10P 354.247)
    → frailty: lead-Wald p = 1.17e-3 (directional)
    → frailty coloc PP.H4 = 0.526 (moderate; PP.H3 0.026)
    => frailty-specific, moderate exploratory candidate signal
   (palindromic-exclusion sensitivity: PP.H4 → 0.051)
   (telomere PP.H4 0.0011 / PP.H3 0.721 = distinct signals; parental longevity PP.H4 0.0044 → not supported)
```

### Limitations
- **Single lead-pQTL Wald ratio**: the MR uses one lead variant and is a
  directional test only — not an LD-clumped multi-instrument IVW (or
  Egger / weighted-median) estimate.
- **Single-causal-variant coloc model**: `coloc.abf()` assumes at most one
  causal variant per locus, which may not hold across the cis-region.
- **Potential UK Biobank sample overlap**: the UKB-PPP pQTL and the aging GWAS
  are derived at least in part from UK Biobank, so exposure-outcome sample
  overlap cannot be excluded and may bias the MR.
- **Palindromic lead-SNP sensitivity**: the C/G palindromic lead rs74510325
  drives the frailty colocalization (PP.H4 0.526 → 0.051 on exclusion).
- **Exploratory, not confirmatory**: confirmation requires independent
  replication in non-UKB frailty / aging cohorts.

---

## 9. Outputs

| Type | Path | Content |
|---|---|---|
| driver | `scripts/run_creld2_pqtl_followup.py` | pQTL locus extraction, pQTL-GWAS harmonization, lead-Wald MR |
| driver | `scripts/run_creld2_coloc_abf.R` | Regional `coloc.abf()` colocalization (primary + palindromic-exclusion) |
| plotting | `scripts/plot_creld2_summary.py` | Summary figures from the tracked result TSVs |
| result | `results/pqtl_locus_manifest.tsv` | Lead variant, locus window, lead significance, locus variant count |
| result | `results/creld2_mr_lead_wald.tsv` | Lead-pQTL Wald-ratio MR per outcome (beta, SE, z, p) |
| result | `results/creld2_coloc_abf.tsv` | Colocalization PP.H0–PP.H4 per outcome (primary + `exclude_palindromic`) |
| provenance | `data_manifest.tsv` | GTEx v8 eQTL, UKB-PPP pQTL, aging GWAS, and gnomAD reference provenance (raw resources not redistributed) |
