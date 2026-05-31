# Methods Draft

## Protocol-driven human genetics evaluation of CRELD2

To evaluate whether PersonaAI-derived hypotheses could be supported by
population-scale genetic evidence, we implemented an agent-assisted,
protocol-driven human genetics evaluation workflow. The workflow followed
predefined steps for hypothesis structuring, data feasibility assessment,
statistical genetics execution, and gap-oriented sensitivity analysis.
Language-model assistance was used to organize candidate evaluation and
document intermediate decisions, whereas all reported statistical estimates were
generated from reproducible Python and R scripts using external summary
statistics.

The workflow was applied to secretory stress-related candidate proteins
nominated from the adipose-liver aging axis, including FGF21, CRELD2, GDF15,
ADIPOQ, and SERPINE1. Candidate proteins were first assessed for tissue-level
regulatory evidence and circulating protein genetic regulation using GTEx v8
cis-eQTL resources and UK Biobank Pharma Proteomics Project (UKB-PPP) plasma
pQTL summary statistics.

For CRELD2, tissue-level regulatory evidence was evaluated in GTEx v8 Adipose
Subcutaneous, Adipose Visceral Omentum, and Liver. Circulating protein
regulation was assessed using UKB-PPP CRELD2 pQTL summary statistics. The
strongest CRELD2 cis-pQTL signal was used to define a +/-500 kb locus for
downstream genetic analyses.

To explore whether CRELD2-related genetic variation was associated with
aging-related phenotypes, we analyzed three GWAS outcomes: frailty index,
leukocyte telomere length, and parental longevity. These outcomes were selected
to represent complementary dimensions of aging, including systemic functional
decline, cellular aging-related genomic maintenance, and lifespan-related
genetic propensity.

CRELD2 pQTL summary statistics were harmonized with each aging GWAS at the
variant level. Because the aging GWAS datasets were aligned to GRCh37
coordinates, pQTL-GWAS matching was performed using the corresponding GRCh37
variant positions. Alleles were aligned to the pQTL effect allele before
downstream analysis.

Directional genetic associations between circulating CRELD2 and aging-related
outcomes were estimated using a lead pQTL-based Wald ratio Mendelian
randomization approach. This analysis was used as an exploratory test of
directionality rather than as definitive multi-instrument causal inference.

Bayesian colocalization analysis was then performed to evaluate whether CRELD2
pQTL and aging GWAS signals were consistent with a shared causal variant.
Colocalization was conducted across the CRELD2 cis-locus using `coloc.abf()`.
Posterior probability for hypothesis 4 (PP.H4) was interpreted as evidence for a
shared causal variant, with PP.H4>0.8 considered strong support and PP.H4>0.5
considered moderate support.

Because the CRELD2 lead pQTL rs74510325 is a C/G palindromic variant, allele
orientation was evaluated using allele-frequency consistency across the pQTL
dataset, the frailty GWAS, and gnomAD reference frequencies. The variant was
retained in the primary harmonized analysis because its minor allele frequency
was consistent across datasets and sufficiently distant from 0.5 to resolve
strand ambiguity. As a sensitivity analysis, colocalization was repeated after
excluding palindromic variants to assess whether the CRELD2-frailty signal
depended on this frequency-resolved lead variant.

All analyses were interpreted as exploratory genetic evaluation rather than
definitive causal inference. Because the UKB-PPP pQTL dataset and the
aging-related GWAS outcomes were derived at least in part from UK Biobank,
potential exposure-outcome sample overlap was considered a limitation.
Independent replication in non-UKB frailty or aging cohorts will be required to
confirm the CRELD2-frailty association.
