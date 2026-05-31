# Statistical Genetics Execution Card

## Purpose

This card maps a feasible human genetics hypothesis to deterministic analysis
scripts.

## Analysis Modules

- Tissue cis-eQTL evidence review.
- Circulating pQTL locus extraction.
- Allele harmonization between pQTL and aging GWAS summary statistics.
- Lead-variant Wald ratio Mendelian randomization.
- Bayesian regional colocalization using `coloc.abf()`.

## Decision Rules

1. Use the molecular QTL effect as the exposure estimate.
2. Use matched GWAS effect estimates as outcome estimates.
3. Interpret single-lead-variant MR as directional evidence rather than
   definitive causal inference.
4. Use colocalization to distinguish shared regional signal from coincident but
   distinct association signals.

## CRELD2 Application

The workflow generated a CRELD2 pQTL locus manifest, harmonized the lead pQTL
against aging GWAS outcomes, calculated Wald ratio estimates, and performed
regional colocalization across the CRELD2 cis-locus.
