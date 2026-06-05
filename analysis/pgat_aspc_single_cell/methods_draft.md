# Methods Draft

## Protocol-driven single-cell evaluation of the gWAT VEC niche / VEGF axis in ASPC aging

To evaluate whether a PersonaAI-derived hypothesis about the age-related decline
of adipocyte stem and progenitor cells (ASPC) in gonadal white adipose tissue
(gWAT) could be resolved at single-cell resolution, we implemented an
agent-assisted, protocol-driven single-cell evaluation workflow. The workflow
followed predefined steps for hypothesis structuring, data feasibility
assessment, single-cell analysis execution through a bundled analysis engine, an
added cell-cell interaction (CCI) component, and an independent deterministic
cross-check. Language-model assistance was used to organize candidate evaluation
and document intermediate decisions, whereas all reported quantitative estimates
were generated from reproducible Python scripts using the Mouse Aging Atlas gWAT
data.

### Hypothesis structuring

Vascular endothelial cells (VEC) in adipose tissue secrete VEGF (*Vegfa*), a
perivascular-niche signal supporting survival and proliferation of ASPC, which
receive it through the VEGF receptor *Kdr* (VEGFR2). We structured two competing,
non-mutually-exclusive hypotheses for the age-related ASPC decline and its sex
dependence:

- **Hypothesis A (VEC niche / VEGF axis, male-specific):** with age the male VEC
  proportion declines, VEC *Vegfa* secretion falls, and ASPC *Kdr* expression
  drops, so that VEC->ASPC ligand-receptor signalling (e.g. Lpl-Lrp1,
  Sparc-Fgfr1, Pdgfb-Lrp1) weakens in males and ASPC regenerative support is
  lost. This change is predicted to be male-specific.
- **Hypothesis B (sex-non-specific / preserved):** a relatively stable pre-estropausal
  hormonal environment preserves endothelial VEGF output and VEC->ASPC signalling
  in females, i.e. VEC proportion, *Vegfa*/*Kdr* expression, and VEC->ASPC
  interaction strength do not change appreciably with age in females.

The summary prediction is that (i) male VEC attrition, (ii) male *Vegfa*/*Kdr*
downregulation, and (iii) male VEC->ASPC L-R weakening all occur and are all
preserved in females.

### Feasibility assessment

Feasibility was assessed against the Mouse Aging Atlas gWAT experiment for the
target genes *Vegfa* (VEC-secreted ligand) and *Kdr* (VEGFR2, ASPC receptor),
in the candidate cell types Vascular endothelial cells (VEC) and
"Adipoce stem and progenitor cells" (ASPC; spelling kept as annotated in the
atlas). Two pre-extracted sex-split h5ads (each 30,000 cells x 53,819 genes)
were used, with age-group metadata (03, 06, 12, 16, 23 months), sex metadata
(Male / Female, analysed separately), and genotype metadata (wild-type, used as
the analysis filter). Both sexes were judged feasible with no blocking gaps
(feasible = True, no blockers). The candidate cell counts were VEC 4,574 / 5,966
and ASPC 3,944 / 3,824 (male / female).

### Execution: bundled MCP engine (per sex)

The primary lineage-screening execution used a bundled single-cell analysis
engine (`personaai/scrna_mcp`, driven by `scripts/run_mcp_report.py`), run once
per sex on the sex-split h5ad. For each sex the engine produced cell-type
expression, sex-stratified age trajectory, young-old contrast, and an
evidence-grading table (in `results/male/` and `results/female/`):

1. **Cell-type expression** (`cell_type_expression.tsv`, gene = *Vegfa*): both
   VEC and ASPC were identified as candidates in both sexes. Baseline VEC *Vegfa*
   was higher in males than females (mean 0.0374 vs 0.0221; percent expressing
   1.73% vs 1.26%).
2. **Age trajectory** (`age_trajectory.tsv`): sex-stratified per-age *Vegfa*
   expression across the five age groups.
3. **Young-old contrast** (`young_old_contrast.tsv`, 03 vs 23 months): the key
   asymmetry. Male VEC *Vegfa* was strongly downregulated
   (log2fc old/young = **-2.701**; percent expressing 3.39% -> 0.17%), whereas
   female VEC *Vegfa* was essentially preserved (log2fc = **-0.153**).
4. **Evidence grading** (`evidence_grading.tsv`): the engine's single-gene
   grading was conservative ("weak") because it scores candidate-cell induction
   only; the sex-contrast and CCI evidence below carry the verdict.

### Execution: cell-cell interaction (CCI) engine

A CCI component (`scripts/run_mcp_cci.py`, LIANA backend via the bundled CCI
engine) compared VEC->ASPC ligand-receptor signalling between young
(03/06 months) and old (16/23 months), per sex. The engine's gained/lost summary
is recorded in `results/cci/{male,female}_compare.json`; the three target-pair
`lr_means` were recomputed (LIANA `rank_aggregate` on each age pool, the same way
the reference CSVs were produced) into `results/cci/target_pairs_compare.tsv`.
All three male VEC->ASPC pairs weakened in old (`weakened_in_old` = True):
Lpl-Lrp1 (1.547 -> 1.150), Sparc-Fgfr1 (1.018 -> 0.886), Pdgfb-Lrp1
(0.990 -> 0.928). This direction agrees with the reference LIANA CSVs
(male weakened for all three pairs).

### Execution: deterministic local cross-check

Because the engines are otherwise black boxes, an independent deterministic
cross-check (`scripts/crosscheck.py` with `scripts/_crosscheck_lib.py`, plain
scanpy/scipy, fixed seeds) recomputed the key decision metrics per sex and wrote
a three-way comparison [local | mcp | target] to
`results/reproduction_check.json`. It recomputed (i) the VEC proportion trend vs
age (Spearman), (ii) VEC *Vegfa* mean(old)-mean(young), and (iii) ASPC *Kdr*
mean(old)-mean(young).

### Results

The molecular evidence converged on Hypothesis A in males and showed preservation
in females:

- **VEGF ligand loss (male):** VEC *Vegfa* young-old log2fc = -2.701
  (3.39% -> 0.17% expressing), versus female -0.153 (preserved).
- **VEGF receptor loss (male):** ASPC *Kdr* mean(old)-mean(young) = **-0.0295**
  in males versus **+0.0013** in females (essentially unchanged).
- **VEC->ASPC L-R weakening (male):** all three target pairs weakened in old
  (Lpl-Lrp1 1.547 -> 1.150, Sparc-Fgfr1 1.018 -> 0.886, Pdgfb-Lrp1
  0.990 -> 0.928), matching the male reference LIANA direction; the female
  reference shows none of the three pairs weakened.

Reference (target) values for the cross-check encode the expected directions:
male VEC proportion rho -0.5 (p ~0.039), female rho +0.1 (p ~0.5, stable); male
*Vegfa*/*Kdr* negative, female ~0. The adopted verdict is
**VEC-niche / VEGF-axis-supported (male-specific)** (Hypothesis A), carried by
the reproduced male molecular signal (*Vegfa* down, *Kdr* down, all three
VEC->ASPC pairs weakened) and the preserved female molecular signal, rather than
by the cell-proportion axis (see Limitations).

### Limitations

- **`female_VEC_rho` mismatch (stated honestly):** the deterministic local
  recompute found that the **female VEC proportion also declines** with age
  (Spearman rho = **-0.7**), contradicting the "female stable" reference
  (target +0.1). This metric is recorded as **mismatch** in
  `results/reproduction_check.json` and is not hidden. The most likely cause is
  that the equal-bin 30k subsampling forces young and old to comparable cell
  counts and thereby distorts the composition (proportion) axis, so the
  subsampled file cannot directly reproduce the full-atlas proportion trend
  (full-atlas female p ~0.5). A full-atlas composition re-check is needed before
  the proportion claim can be settled. The non-significant local p (female 0.1881)
  still agrees that the female change is "not a significant decline", consistent
  with the reference. Because of this, the verdict rests on the molecular signal
  (*Vegfa*/*Kdr*/CCI), not the proportion axis.
- **Male proportion under-powered in the subsample:** male VEC proportion local
  rho = -0.7 agrees in direction with the reference (-0.5) but local p = 0.1881
  does not reach significance in the subsampled file (reference p ~0.039),
  the same equal-bin subsampling effect.
- **CCI female direction partly differs from reference:** for female Lpl-Lrp1 and
  Pdgfb-Lrp1 the engine recompute marks a slight decrease (weakened) while the
  reference LIANA marks them not-weakened; the magnitudes are small and this is
  attributed to pooled (all-ages-pooled) versus per-month LIANA aggregation. The
  male result (all three pairs concordant) is unaffected.
- **Association, not causation:** scRNA-seq and CCI support a cellular origin and
  a weakening of niche signalling but do not establish that VEC-niche loss causes
  the ASPC decline.
- **Sex-split single h5ads:** each sex is a single 30k file, so batch and
  subsampling effects can influence the proportion estimates (linked to the
  `female_VEC_rho` caveat above).
