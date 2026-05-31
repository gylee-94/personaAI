# Protocol-Driven Human Genetics Evaluation

This protocol describes the public-facing version of the hypothesis evaluation
workflow used for the CRELD2 analysis. It abstracts the internal agent operating
instructions into a reproducible statistical genetics workflow.

For protocol provenance, see `protocol_library_manifest.tsv` and the
`human_genetics_skill_cards/` directory. These files define the reusable
decision rules that link agent-assisted hypothesis evaluation to deterministic
analysis scripts.

## 1. Hypothesis Structuring

Candidate mechanisms are converted into testable components. For the CRELD2
analysis, the biological claim was reframed as a population-genetics question:
whether genetic regulation of circulating CRELD2 is linked to aging-related
phenotypes.

## 2. Data Feasibility Assessment

Each candidate is checked for available evidence layers:

- tissue-level cis-eQTL evidence
- circulating protein pQTL evidence
- aging-related GWAS outcome availability
- regional summary statistics sufficient for colocalization
- allele frequency, genome build, and sample size metadata

Unavailable evidence layers are treated as limitations rather than inferred from
weaker data.

## 3. Statistical Genetics Execution

The workflow maps each feasible component to deterministic R or Python scripts.
For CRELD2, this included:

- GTEx v8 tissue cis-eQTL review
- UKB-PPP plasma pQTL extraction
- pQTL-GWAS allele harmonization
- lead pQTL-based Wald ratio Mendelian randomization
- Bayesian colocalization with `coloc.abf()`

Language-model assistance may be used to organize the workflow and draft code,
but statistical estimates are generated only by executed scripts.

## 4. Gap-Oriented Sensitivity Analysis

Open issues identified during execution are re-evaluated when addressable. In
the CRELD2 workflow, the main sensitivity analysis concerned the C/G
palindromic lead pQTL rs74510325. The primary analysis retained the variant
because allele frequencies were consistent across pQTL, GWAS, and gnomAD
reference data. A sensitivity analysis repeated colocalization after excluding
palindromic variants.

## 5. Evidence Grading

Results are interpreted as exploratory unless they satisfy strong statistical
and design criteria. For this workflow:

- Wald MR is based on a single lead pQTL and is directional, not definitive.
- `PP.H4 > 0.8` is considered strong colocalization support.
- `PP.H4 > 0.5` is considered moderate support.
- Potential UK Biobank sample overlap is treated as a limitation.

Independent non-UKB replication is required before making confirmatory causal
claims.
