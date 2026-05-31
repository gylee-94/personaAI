# CRELD2 Human Genetics Workflow

This directory contains the public workflow for evaluating CRELD2 as a
circulating candidate linking tissue secretory stress to frailty-associated
systemic decline.

## Analysis Summary

The workflow integrates:

- GTEx v8 cis-eQTL evidence for CRELD2 in adipose subcutaneous tissue, adipose
  visceral omentum, and liver
- UKB-PPP plasma pQTL summary statistics for CRELD2
- GWAS summary statistics for frailty index, leukocyte telomere length, and
  parental longevity
- lead pQTL-based Wald ratio MR
- Bayesian colocalization using `coloc.abf()`
- palindromic SNP sensitivity analysis

DNAm GrimAge was examined during exploratory work but is not included in the
main public workflow because it is not part of the adopted Results section.

## Required External Data

See `data_manifest.tsv`. Raw GTEx, UKB-PPP, and GWAS summary statistics are not
redistributed in this repository.

Expected local layout when reproducing the scripts:

```text
<repo-or-data-root>/
  pQTL/ukbiobank/CRELD2_Q6UXH1_OID20751_v1_Inflammation.tar
  data/aging_gwas/opengwas/metal/
    GCST90020053_frailty_index.metal.tsv.gz
    ieu-b-4879_telomere_length.metal.tsv.gz
    GCST006697_parental_longevity_combined_attained_age.metal.tsv.gz
```

## Reproduction

Generate harmonized locus files and lead-Wald MR summary:

```bash
python analysis/creld2_human_genetics/scripts/run_creld2_pqtl_followup.py \
  --root /path/to/data/root \
  --out analysis/creld2_human_genetics/results/recomputed
```

Run colocalization:

```bash
Rscript analysis/creld2_human_genetics/scripts/run_creld2_coloc_abf.R \
  --out analysis/creld2_human_genetics/results/recomputed
```

Plot summary figures from the tracked summary TSV files:

```bash
python analysis/creld2_human_genetics/scripts/plot_creld2_summary.py \
  --result-dir analysis/creld2_human_genetics/results \
  --out-dir analysis/creld2_human_genetics/figures
```

## Interpretation

The tracked summary results reproduce the main finding: CRELD2 showed a
frailty-specific moderate candidate signal among the tested aging-related
outcomes. The analysis is exploratory because it uses a single lead pQTL Wald
ratio, `coloc.abf()` under a single-causal-variant model, and datasets derived
at least in part from UK Biobank.

## Related Protocol Documents

The analysis should be read together with the public protocol provenance files:

- `../../protocols/human_genetics_evaluation_protocol.md`
- `../../protocols/protocol_library_manifest.tsv`
- `../../docs/supplementary_table6_human_genetics_workflow.tsv`
- `../../docs/table1_llm_scoring_rubric.md`
- `../../docs/agent_assistance_disclosure.md`
