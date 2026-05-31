# Table 1. LLM-Assisted Hypothesis Screening Rubric

This rubric documents the public-facing criteria used to screen generated
hypotheses before in-silico evaluation. It is intended to support transparent
workflow reporting, not to replace statistical validation.

## Scoring Scale

Each hypothesis is assigned a score from 0.0 to 1.0. Hypotheses with scores
greater than or equal to 0.9 are eligible for downstream hypothesis evaluation.

## Criteria

| Criterion | Weight | Description |
| --- | ---: | --- |
| Biological plausibility | 0.25 | The hypothesis is grounded in known aging biology, tissue context, or pathway evidence. |
| Testable exposure and outcome | 0.20 | The hypothesis can be mapped to measurable molecular traits and aging-related outcomes. |
| Evidence coverage | 0.20 | Relevant public datasets are likely to exist across molecular and phenotype layers. |
| Integration quality | 0.20 | The hypothesis connects tissue biology, molecular regulation, and organism-level aging phenotypes coherently. |
| Limitation awareness | 0.15 | The hypothesis identifies likely sources of uncertainty, such as sample overlap, proxy outcomes, or incomplete causal identifiability. |

## CRELD2 Interpretation

The CRELD2 hypothesis passed screening because it linked adipose/liver
secretory stress biology to a measurable circulating protein and to
population-scale aging outcomes. Passing the threshold did not imply that the
candidate was causal; it indicated that the hypothesis was sufficiently
structured and data-feasible for in-silico evaluation.
