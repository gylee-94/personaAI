# CRELD2 lead-variant alignment and recorded scope

`results/lead_variant_alignment_record.tsv` transcribes the approximate values
reported in the final manuscript and Supplementary Table 10. It is a source
record, not a new extraction from raw GWAS data. The pQTL effect allele is G
(frequency about 0.0348); the frailty GWAS effect allele is C (0.9653), so its G
frequency is 1 - 0.9653 = 0.0347. The recorded decision aligned outcome effects
to G and reversed signs when allele order was opposite. GRCh37 position is
22:50315382; the pQTL GENPOS field is GRCh38 22:49921734.

The historical gnomAD check was described in older methods, but a numeric
frequency with reference population/version was not recovered. It is therefore
not an independently verifiable third-frequency check in this release. The
transcribed pQTL/GWAS values alone should not be presented as a newly executed
full harmonization audit.

The Python harmonizer matches single-base allele sets and reverses the outcome
beta on an allele-order swap. It does not perform strand-complement inference
or frequency-based automatic resolution. New outputs preserve original GWAS
alleles/EAF, aligned EAF, the absolute frequency difference, and a manual-review
flag for palindromic variants. Duplicate outcome positions now fail explicitly
rather than silently selecting the last record; resolve them by variant and
alleles before analysis. These code changes have not re-estimated the archived
results. The original five-candidate drivers are retained under
`scripts/hypothesis4_original/` for provenance.

Sensitivity removed all 478 palindromic variants (3,595 to 3,117), including the
lead. The reduced PP.H4 does not isolate the lead SNP's contribution and does
not establish an alignment error. Neither the primary nor sensitivity result
establishes a causal, frailty-specific effect.
