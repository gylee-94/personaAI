# PGAT: secondary VEC–ASPC expression and interaction check

Interpretation updated 2026-11-05 from recorded outputs; no atlas reanalysis
was performed for this update. This MCP/local pipeline is separate from the
manuscript's manual analyses and additional mouse-level models. See
[public scope](../../../docs/reproducibility_scope.md).

## 1. Overall interpretation

Recorded male VEC Vegfa and ASPC Kdr expression contrasts are negative, and
three selected male VEC-to-ASPC ligand–receptor scores decline. These are
associations compatible with a vascular-niche hypothesis. This check does not
measure ASPC regenerative capacity, establish VEGFA–KDR signaling activity, or
prove a causal or male-specific mechanism.

The former `VEC-niche / VEGF-axis-supported (male-specific)` verdict was too
strong. Female effects near zero and nonsignificant P values are not tests of
equivalence; a sex difference requires a direct interaction test. Both recorded
sex subsets have a negative VEC age trend. The historical female positive
reference is discordant, and its cause has not been established.

| Question | Recorded observation | Scope |
|---|---|---|
| VEC proportion trend | rho -0.7 and P 0.1881 in each sex | Descriptive age-bin trends; no male-specific decline established here |
| Vegfa/Kdr expression | Larger negative male contrasts; smaller female contrasts | Consistent with the proposed expression pattern; not a sex-interaction test |
| Three selected L–R pairs | All male scores decrease; two female scores also decrease | Pair-specific pooled-cell expression scores |
| VEGFA–KDR and ASPC regeneration | No retained VEGFA–KDR interaction score; no regeneration measurement | Direct mechanism and functional consequence not tested |

## 2. Inputs and contrasts

The recorded inputs are WT `gWAT_male_30k.h5ad` and `gWAT_female_30k.h5ad`, each
30,000 cells by 53,819 genes. VEC counts are 4,574 male/5,966 female and ASPC
counts 3,944/3,824. Cells and age bins are not independent mouse replicates.

| Analysis | Actual contrast and scale |
|---|---|
| MCP expression | 3 versus 23 months; `log2((old_mean+0.01)/(young_mean+0.01))` on stored X |
| Local Vegfa/Kdr | Equally weighted means across <=6 versus >=16-month age bins on stored/normalized X |
| Local VEC trend | Spearman correlation of age-bin proportions with age |
| Secondary CCI | Pooled 3+6 versus 16+23-month cells; LIANA `use_raw=False`, normalization/log1p if X maximum exceeds 50 |
| Primary manuscript CCI | Separate sex/age runs on raw UMI counts, including 3 versus 12-month comparisons; a different calculation |

The MCP age contrast, local mean difference, and manuscript mouse-level model
are different estimands. Their magnitudes should not be treated as replicated
estimates of one effect.

## 3. Cell-type expression (recorded MCP output)

Source: `male/cell_type_expression.tsv`, `female/cell_type_expression.tsv`;
gene = Vegfa.

| sex | cell_type | n_cells | mean_expression | pct_expressing (%) | is_candidate |
|---|---|---:|---:|---:|:---:|
| Male | Adipoce stem and progenitor cells | 3,944 | 0.044371 | 3.0933 | True |
| Male | Vascular endothelial cells | 4,574 | 0.037385 | 1.7272 | True |
| Female | Adipoce stem and progenitor cells | 3,824 | 0.056224 | 3.6088 | True |
| Female | Vascular endothelial cells | 5,966 | 0.022125 | 1.2571 | True |

## 4. Age expression contrasts (recorded MCP output)

Source: `male/young_old_contrast.tsv`, `female/young_old_contrast.tsv`;
3 versus 23 months, gene = Vegfa.

| sex | cell_type | n_young | n_old | young_mean | old_mean | log2fc (old/young) | young_pct (%) | old_pct (%) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Male | Vascular endothelial cells | 1,211 | 590 | 0.066061 | 0.001695 | **-2.7013** | 3.3856 | 0.1695 |
| Male | Adipoce stem and progenitor cells | 497 | 724 | 0.080483 | 0.044199 | -0.7394 | 4.6278 | 3.0387 |
| Female | Vascular endothelial cells | 1,497 | 789 | 0.018036 | 0.015209 | **-0.1533** | 1.2024 | 1.1407 |
| Female | Adipoce stem and progenitor cells | 871 | 477 | 0.073479 | 0.056604 | -0.3258 | 4.4776 | 3.5639 |

The separate local ASPC Kdr contrasts are -0.0295 in males and +0.0013 in
females (>=16 minus <=6 months). These point estimates do not supply
mouse-level uncertainty or a sex-interaction P value.

## 5. Recorded ligand–receptor scores

Source: `cci/target_pairs_compare.tsv`. These three pairs do not measure the
VEGFA–KDR interaction. Vegfa expression in VECs is only about 1.3–1.7% in the
recorded MCP summaries; the proposed pair is not supported by a retained score
under the 10% LIANA expression filter. The final manuscript separately reports
that both ligand and receptor fail this threshold. Low detection is not proof
of no biological signaling.

| sex | ligand | receptor | young_lr_means | old_lr_means | weakened_in_old (MCP) | reference LIANA direction |
|---|---|---|---:|---:|:---:|---|
| male | Lpl | Lrp1 | 1.547464 | 1.149670 | **True** | weakened (agrees) |
| male | Sparc | Fgfr1 | 1.018449 | 0.886089 | **True** | weakened (agrees) |
| male | Pdgfb | Lrp1 | 0.989930 | 0.928418 | **True** | weakened (agrees) |
| female | Lpl | Lrp1 | 0.988269 | 0.953956 | True | not-weakened (differs) |
| female | Sparc | Fgfr1 | 0.648321 | 0.666761 | False | not-weakened (agrees) |
| female | Pdgfb | Lrp1 | 0.650614 | 0.606989 | True | not-weakened (differs) |

The secondary male score changes are approximately -25.7%, -13.0%, and -6.2%
for Lpl–Lrp1, Sparc–Fgfr1, and Pdgfb–Lrp1, respectively. Female changes are
-3.5%, +2.8%, and -6.7%. In particular, the female Pdgfb–Lrp1 decrease is
similar in relative size to the male decrease; it cannot be dismissed as
negligible to support male specificity. These scores have no mouse-level
uncertainty. The historical reference directions and the two female
disagreements remain visible. Different aggregation/normalization may matter,
but their causal role in the discrepancies was not established.

## 6. Execution and evidence boundary

| Stage | Public output | Scope |
|---|---|---|
| MCP expression | `male/` and `female/` TSVs | Descriptive expression summaries |
| CCI | `cci/target_pairs_compare.tsv`, `cci/male_compare.txt`, `cci/female_compare.txt` | Pooled-cell scores and unchanged textual engine logs |
| Local comparison | `reproduction_check.json` | Direction/significance categories; not numerical replication |
| Manuscript mouse-level models | Manuscript results and methods | Additional analysis; exact generating scripts not recovered here |

## 6b. Direction and significance comparison

| Local estimand | Local value | Historical reference/expectation | Comparison |
|---|---:|---|---|
| Male VEC age-bin rho | -0.7 | -0.5 | Directionally concordant |
| Male VEC trend P | 0.1881 | 0.039 | Significance-category disagreement |
| Male VEC Vegfa mean difference | -0.03881 | Expected decrease (legacy -1 placeholder) | Directionally concordant; no numerical target |
| Male ASPC Kdr mean difference | -0.0295 | Expected decrease (legacy -1 placeholder) | Directionally concordant; no numerical target |
| Female VEC age-bin rho | -0.7 | +0.1 | Directionally discordant |
| Female VEC trend P | 0.1881 | 0.5 | Same nonsignificant category; not equivalence |
| Female VEC Vegfa mean difference | -0.0107 | Approximately unchanged (legacy 0 placeholder) | Not assessable without an equivalence margin/test |
| Female ASPC Kdr mean difference | +0.0013 | Approximately unchanged (legacy 0 placeholder) | Not assessable without an equivalence margin/test |

The separate MCP Vegfa contrasts (-2.701278 male, -0.153338 female) are log2
mean-expression ratios for 23/3 months, not the local mean differences above.
JSON retains them with explicit estimand metadata. The original local numbers
are unchanged; the old labels are retained as `legacy_match`.

## 7. Interpretation limits

The female VEC discrepancy cannot be assigned to subsampling without testing
that explanation. The final manuscript's separate mouse-level analysis reports
negative long-term VEC age trends in both sexes; that result should not be
replaced by the older "female stable" target. Likewise, the manuscript's
3–6 versus 12-month expression/abundance tests differ from this secondary
pipeline's age grouping.

The hypothesis remains a proposal consistent with some expression observations.
These pooled-cell scores do not demonstrate ligand–receptor binding, ASPC
regenerative decline, or its causal origin. No direct functional rescue or
perturbation experiment is contained in this report. Negative, discordant and
unassessable comparisons are retained together with supportive observations.

## 8. Outputs and reuse

[scripts/run_mcp_report.py](../scripts/run_mcp_report.py) drives the per-sex
expression summaries, [scripts/run_mcp_cci.py](../scripts/run_mcp_cci.py) produces
the CCI scores/text logs, and [scripts/crosscheck.py](../scripts/crosscheck.py)
produces the comparison JSON. Input requirements are in `data_manifest.tsv`.
These scripts support the secondary calculations described here, not exact
reproduction of the manual manuscript analysis.
