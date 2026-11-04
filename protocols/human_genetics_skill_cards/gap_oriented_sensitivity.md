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

The CRELD2 lead rs74510325 is a low-frequency C/G palindromic variant. Its
reported pQTL G frequency (approximately 0.0348) agrees with the frailty GWAS G
frequency (0.0347 after converting the reported C frequency). Those values are
transcribed in the alignment record. Exact numeric/version records for the
historically mentioned external reference checks were not recovered.

Sensitivity removed all 478 palindromic variants, including the lead, and
lowered PP.H4 from 0.526 to 0.051. It did not isolate the lead's contribution
or establish an alignment error. The 0.5/0.8 posterior thresholds describe
reporting categories, not verified prospective registration. Original
numerical outputs remain unchanged.
