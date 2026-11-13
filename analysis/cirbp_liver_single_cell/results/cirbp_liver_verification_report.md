# CIRBP liver: secondary single-cell evidence check

Interpretation updated 2026-11-05 from existing outputs; no atlas reanalysis
was performed for this update. This report describes a secondary MCP/local
pipeline. The primary manuscript analyses were performed manually; their
mouse-level models are distinct (see [public scope](../../../docs/reproducibility_scope.md)).

Availability note (2026-11-13): the authors have now supplied the additional
primary revision scripts, logs, and per-mouse tables under
[../revision/](../revision/README.md). The numerical secondary results below
remain unchanged.

## 1. Overall interpretation

The recorded extract favors a hepatocyte-associated age contrast. Hepatocytes
have a positive old-minus-young expression difference, while the myeloid
contrast is negative. The historical label `hepatocyte-supported` describes
this pattern. It is not a statistical test of cell of origin or proof that
hepatocyte stress causes the bulk-tissue increase. Myeloid upregulation is not
supported in this extract; immune contributions cannot be excluded.

| Question | Observation | Supported scope |
|---|---|---|
| Hepatocyte age-associated expression | Stored-scale log2 ratio +1.5555; expressing fraction 0% to 1.697% | Positive descriptive contrast in the extract |
| Myeloid age-associated expression | Stored-scale log2 ratio -2.4190; 23 young cells and 175 old cells | No induction observed; only one young myeloid cell expressed Cirbp, so this does not reject an immune mechanism |
| Age enrichment of a re-derived cluster | OR 8.273 for pooled 16+23-month cells; 83.54% of the cluster is in those ages | Age composition of a separately selected cluster, not reproduction of manuscript C4 |
| Stress markers | Cdkn1a, Cirbp, Xbp1 and Atf4 ratios exceed 1 | Limited marker observations, not proof of senescent-cell identity |

## 2. Inputs and estimands

The MCP lineage record contains 3,736 cells (3,390 hepatocytes and 346 myeloid
cells), a single-gene expression extract, and WT age/sex annotations. The
reported counts total 339, 1,000, 1,000, 397 and 1,000 cells at 3, 6, 12, 16 and
23 months; 1,907 female and 1,829 male cells. These are cell counts, not numbers
of independent animals.

The local cross-check uses `liver_hepatocyte_myeloid_full.h5ad` for its cell-level
Spearman trend and a multi-gene `liver_hepatocyte_myeloid_comparison.h5ad` for
clustering. These historical basenames do not establish that the single-gene
MCP input and multi-gene clustering input are identical snapshots. Raw objects
and immutable input hashes are not bundled.

For the secondary cluster search, the script uses up to 4,000 cells, seed 0,
2,000 HVGs, 30 PCs, and Leiden resolution 1.0, then selects the cluster with
the highest age-enrichment OR. Its old group pools 16 and 23 months. The
manual historical reference has 2,372 hepatocytes, 40 PCs, 15 neighbors,
resolution 0.5 and a 23-month contrast. Differences cannot be assigned solely
to random seed or software version. Cluster selection by the largest OR is
exploratory; its Fisher P value is not a prespecified cluster test.

## 3. Cell-type expression (recorded MCP output)

Source: `cell_type_expression.tsv`.

| cell_type | n_cells | mean_expression | median | pct_expressing (%) | is_candidate |
|---|---:|---:|---:|---:|:---:|
| Hepatocytes | 3,390 | 0.013274 | 0.0 | 0.9735 | True |
| Myeloid cells | 346 | 0.008671 | 0.0 | 0.5780 | True |

## 4. Age summaries (recorded MCP output)

Sources: `age_trajectory.tsv` and `young_old_contrast.tsv`. The trajectory table
summarizes the input across cell types; it is not a hepatocyte-specific
mouse-level trend. The highest female expressing fraction is at 16 months,
whereas the highest male fraction is at 23 months.

| sex | age_group | n_cells | mean_expression | pct_expressing (%) |
|---|---|---:|---:|---:|
| Female | 03_months | 178 | 0.005618 | 0.5618 |
| Female | 06_months | 448 | 0.011161 | 0.8929 |
| Female | 12_months | 466 | 0.010730 | 0.4292 |
| Female | 16_months | 257 | 0.019455 | 1.1673 |
| Female | 23_months | 558 | 0.010753 | 1.0753 |
| Male | 03_months | 161 | 0.000000 | 0.0000 |
| Male | 06_months | 552 | 0.018116 | 1.0870 |
| Male | 12_months | 534 | 0.011236 | 0.9363 |
| Male | 16_months | 140 | 0.000000 | 0.0000 |
| Male | 23_months | 442 | 0.022624 | 1.8100 |


| cell_type | n_young | n_old | young_mean | old_mean | log2fc (old/young) | young_pct (%) | old_pct (%) |
|---|---:|---:|---:|---:|---:|---:|---:|
| Hepatocytes | 316 | 825 | 0.0 | 0.019394 | **+1.5555** | 0.0 | 1.6970 |
| Myeloid cells | 23 | 175 | 0.043478 | 0.0 | **-2.4190** | 4.3478 | 0.0 |

The contrast column named `log2fc_old_vs_young` is
`log2((old_mean + 0.01)/(young_mean + 0.01))` on the stored X scale. It is not a
raw-count fold change or a donor-level model estimate. A zero mean from sparse
cells should not be interpreted as biological absence.

## 5. Re-derived cluster observations

Source: `reproduction_check.json`. The recorded cluster has 83.54% pooled
16+23-month cells and OR 8.273. Its mean-X ratios against other clusters are
Cdkn1a 7.811, Cirbp 3.748, Xbp1 2.599 and Atf4 1.046. The script calculates
`(mean_X_cluster + 1e-9)/(mean_X_rest + 1e-9)` after its normalization check.
These ratios on a stored/log-normalized scale should not be read as raw-count
fold changes. The markers are compatible with stress-associated transcription,
without establishing an irreversible senescent state or causal mechanism.

## 6. Execution and evidence boundary

| Stage | Public record | Interpretation |
|---|---|---|
| MCP lineage screen | `cell_type_expression.tsv`, `age_trajectory.tsv`, `young_old_contrast.tsv` | Descriptive cell summaries |
| Historical automatic grade | `evidence_grading.tsv` | Original label retained; current code additionally requires positive change, complete candidates and nonempty age groups |
| Local comparison | `scripts/crosscheck.py`, `reproduction_check.json` | Secondary directional comparison with a different design |
| Primary mouse-level inference | `../revision/scripts/` and `../revision/results/` | Author-supplied additional analyses and per-mouse tables; separate from this secondary report; processed h5ad inputs remain external |

## 6b. Direction and significance comparison

Source: `reproduction_check.json`; reference values are traceable to the
[unchanged historical summary](../reference/README.md). The legacy filename
is retained; current labels do not mean numerical reproduction.

| Local estimand | Recorded local value | Historical reference | Comparison performed |
|---|---:|---:|---|
| Cell-level Spearman rho | 0.0331 | 0.042 | Positive direction in both |
| Cell-level Spearman P | Rounded to 0 at five decimals; exact P unavailable | 0.040 | Both in the P < 0.05 category; not a numeric match |
| Selected cluster old-age fraction | 83.54% | 73.1% | Both above 50%, with different old-age definitions; this threshold alone is not an enrichment test |
| Selected cluster OR | 8.273 | 14.98 | Both above 1, with different contrasts/clusters |
| Cdkn1a mean-X ratio | 7.811 | 5.48 | Both above 1 |
| Cirbp mean-X ratio | 3.748 | 2.03 | Both above 1 |
| Xbp1 mean-X ratio | 2.599 | 2.01 | Both above 1 |
| Atf4 mean-X ratio | 1.046 | 1.51 | Both above 1 |

The MCP age-contrast value 1.555519 is a log2 mean-expression ratio, not a
Spearman rho. It is retained in JSON with its own estimand metadata and is not
an additional estimate of rho. Agreement in these directions does not validate
the magnitude, significance, independence, or biological mechanism.

## 7. Limits and outputs

The myeloid comparison is sparse, the cluster was selected after inspecting
age enrichment, and the analyses share atlas data. This is not independent
biological replication. Broad myeloid annotation is not a cell-specific Kupffer
assay. The current grade is descriptive and does not adjust for mouse-level
clustering, sex, or power. The generic-looking inline parser has CIRBP/liver
case defaults and requires review of its parsed specification.

Original numerical outputs and reference disagreements are retained.
[scripts/crosscheck.py](../scripts/crosscheck.py) writes the comparison JSON;
[scripts/run_mcp_report.py](../scripts/run_mcp_report.py) drives the secondary
engine. Future runs can change values with different inputs/settings; updating
these helpers has not rerun the archived experiment.
