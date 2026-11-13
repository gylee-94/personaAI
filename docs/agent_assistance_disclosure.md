# Agent assistance and analysis roles

The manuscript's primary single-cell analyses were performed manually. The
single-cell MCP runs in this repository are separate secondary checks, with
an agent organizing tasks and deterministic code calculating the reported
extract-level summaries. The phrase "MCP execution" refers to that secondary
pipeline, not to replacement of the manuscript's manual analysis.

Author-supplied scripts for the additional primary Figure 3 and Figure 4
revision statistics are available in the case directories under `revision/`.
They run the documented statistical calculations without an LLM runtime and
are separate from the secondary MCP pipeline. Their supplied logs and per-mouse
tables are preserved; repository integration did not rerun the full analyses.

Agents assisted hypothesis structuring, workflow selection, retrieval,
interpretation, and report drafting. For the Figure 2 RAG work, people wrote
user prompts and recorded outputs. The historical-literature novelty screen
and later-literature verification were also RAG-assisted. These activities do
not constitute independent, blinded expert assessment.

Human-genetics estimates were calculated by Python/R drivers. The complete
five-candidate screen and original outputs are available under
`analysis/creld2_human_genetics/results/five_candidate_screen/`. A single-variant
MR association and moderate coloc evidence are exploratory, not proof of
causation or frailty specificity.

Secondary single-cell checks compare directions and significance categories
with historical references. Correlations, expression contrasts, cluster odds
ratios, and mouse-level models are different estimands. Agreement in sign is
not numerical reproduction or independent biological replication. A
nonsignificant female result does not establish sex specificity or equivalence;
a mismatch cannot be attributed to subsampling without testing that explanation.

Current reports distinguish recorded estimates from interpretation. Original
numerical results, negative comparisons, and sensitivity outputs are retained.
See [reproducibility_scope.md](reproducibility_scope.md) for available source
records, remaining primary-analysis input/code requirements, and historical RAG
limitations.
