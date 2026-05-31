# Gap-Oriented Sensitivity Card

## Purpose

This card defines how unresolved analysis risks are reviewed after initial
execution.

## Common Gap Classes

- Ambiguous strand or palindromic variants.
- Incomplete allele frequency metadata.
- Potential sample overlap.
- Weak instrument or single-instrument MR constraints.
- Colocalization support below strong evidence thresholds.
- Outcome definitions that are related but not equivalent.

## Decision Rules

1. Address gaps with targeted sensitivity analyses when the required data are
   available.
2. Keep unresolved gaps as limitations instead of overstating the evidence.
3. Prefer allele-frequency informed harmonization over automatic exclusion when
   the variant is palindromic but frequency evidence is consistent.
4. Report whether sensitivity analyses materially change the inference.

## CRELD2 Application

The CRELD2 lead pQTL rs74510325 is a palindromic C/G variant. The primary
analysis retained it because pQTL, GWAS, dbSNP/PAGE, and gnomAD allele
frequencies were consistent. A sensitivity analysis excluding palindromic
variants showed reduced colocalization support, indicating that the lead
variant strongly influenced the regional result.
