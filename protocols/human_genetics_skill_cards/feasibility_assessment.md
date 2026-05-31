# Feasibility Assessment Card

## Purpose

This card defines whether a candidate hypothesis has enough compatible public
genetic evidence for downstream analysis.

## Evidence Checks

- cis-eQTL availability in biologically relevant tissues.
- Plasma or serum pQTL availability for the candidate protein.
- Aging-related GWAS summary statistics with allele, effect, frequency, and
  sample size information.
- Regional summary statistics around the molecular QTL for colocalization.
- Consistent genome build, coordinate interpretation, and variant identifiers.

## Decision Rules

1. Proceed only with evidence layers that can be mapped to reproducible data
   sources.
2. Do not infer missing layers from unrelated proxy datasets.
3. Record limitations when phenotype definitions, ancestry, or cohort overlap
   affect interpretation.
4. Exclude an outcome from the main report when it is not suitable for the
   stated validation role.

## CRELD2 Application

GTEx v8 was used for tissue cis-eQTL context in adipose and liver tissues.
UKB-PPP provided circulating CRELD2 pQTL evidence. Frailty index, leukocyte
telomere length, and parental longevity GWAS were retained as complementary
aging-related outcomes. DNAm GrimAge was not included in the public main
workflow because it was not used as a primary reported validation outcome.
