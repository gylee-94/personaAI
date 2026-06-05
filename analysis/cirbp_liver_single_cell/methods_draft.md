# Methods Draft

## Protocol-driven single-cell evaluation of liver CIRBP cell-of-origin

To evaluate whether a PersonaAI-derived hypothesis about age-related liver CIRBP
upregulation could be resolved at single-cell resolution, we implemented an
agent-assisted, protocol-driven single-cell evaluation workflow. The workflow
followed predefined steps for hypothesis structuring, data feasibility
assessment, single-cell analysis execution through a bundled analysis engine,
and an independent deterministic cross-check. Language-model assistance was used
to organize candidate evaluation and document intermediate decisions, whereas
all reported quantitative estimates were generated from reproducible Python
scripts using the Mouse Aging Atlas liver data.

### Hypothesis structuring

Bulk evidence indicates that the cold-inducible RNA-binding protein gene
(*Cirbp*) is upregulated in liver tissue with age. *Cirbp* is induced under a
range of cellular stresses, so its age-related increase in bulk liver could
reflect either a hepatocyte-intrinsic stress response or an immune/myeloid
inflammatory response. We therefore structured two competing, non-mutually
exclusive hypotheses for the cell of origin:

- **Hypothesis A (hepatocyte stress):** the age-related liver *Cirbp* increase is
  driven by hepatocytes adapting to intrinsic metabolic, oxidative, and ER
  stress. This predicts age-dependent *Cirbp* induction within hepatocytes and an
  aged-enriched hepatocyte subcluster carrying senescence (*Cdkn1a*) and ER /
  integrated stress (*Xbp1*, *Atf4*) signatures.
- **Hypothesis B (Kupffer/myeloid immune):** the increase is driven by
  inflammaging in resident macrophages (Kupffer cells) and other myeloid cells.
  This predicts that myeloid cells, not hepatocytes, show the strongest
  age-dependent *Cirbp* upregulation.

### Feasibility assessment

Feasibility was assessed against the Mouse Aging Atlas Liver experiment for the
target gene *Cirbp* (exact var-name match). The atlas-derived liver subset used
for cell-type expression and contrast analysis comprised 3,736 cells across two
candidate cell types, Hepatocytes (3,390 cells) and Myeloid cells (346 cells),
with age-group metadata spanning 03, 06, 12, 16, and 23 months, sex metadata
(Female / Male, both available for stratification), and genotype metadata
(wild-type, used as the analysis filter). The hypothesis was judged feasible with
no blocking gaps in required metadata.

### Execution: bundled MCP engine

The primary execution used a bundled single-cell analysis engine
(`personaai/scrna_mcp`, driven by `scripts/run_mcp_report.py`) under a lineage
screening intent. The engine produced four tracked tables (in `results/`):

1. **Cell-type expression** (`cell_type_expression.tsv`): hepatocytes showed
   higher *Cirbp* than myeloid cells in both mean expression (0.01327 vs 0.00867)
   and percent expressing (0.973% vs 0.578%).
2. **Age trajectory** (`age_trajectory.tsv`): sex-stratified per-age expression;
   the highest percent-expressing values occurred at 23 months (Male 1.810%,
   Female 1.075%), and the single highest mean expression was Male 23 months
   (0.02262).
3. **Young-old contrast** (`young_old_contrast.tsv`, 03 months vs 23 months): the
   direction of age induction was opposite between cell types. Hepatocytes
   increased with age (log2fc old/young = **+1.556**; percent expressing
   0.0% -> 1.697%), whereas myeloid cells decreased (log2fc old/young =
   **-2.419**; percent expressing 4.348% -> 0.0%).
4. **Evidence grading** (`evidence_grading.tsv`): the verdict was
   **hepatocyte-supported**, with the rationale that hepatocytes show both
   dominant expression and the strongest aging induction.

### Execution: deterministic local cross-check

Because the engine is otherwise a black box, an independent deterministic
cross-check (`scripts/crosscheck.py` with `scripts/_crosscheck_lib.py`,
plain scanpy/scipy, fixed seeds) recomputed the key decision metrics and wrote a
three-way comparison [local | mcp | target] to `results/reproduction_check.json`.
The cross-check (i) recomputed the hepatocyte *Cirbp* age trend on the lineage
h5ad and confirmed a positive Spearman trend consistent in sign with the engine's
positive hepatocyte log2fc, and (ii) identified an aged-enriched hepatocyte
subcluster on the comparison h5ad and characterized its stress phenotype. The
top subcluster was strongly aged-enriched (aged fraction 83.54%, 23-month
enrichment odds ratio 8.273), and that subcluster showed elevated senescence and
stress markers as fold-changes (top-cluster / rest): *Cdkn1a* 7.811x, *Cirbp*
3.748x, *Xbp1* 2.599x, and *Atf4* 1.046x.

### Results

The three lines of evidence converged on Hypothesis A. Hepatocytes dominated
baseline *Cirbp* expression, were the only cell type with positive age induction
(log2fc +1.556 vs myeloid -2.419), and contained an aged-enriched subcluster
(83.54% aged, OR 8.273) bearing senescence (*Cdkn1a* 7.811x) and ER / integrated
stress (*Xbp1* 2.599x, *Atf4* 1.046x) signatures alongside *Cirbp* itself
(3.748x). The myeloid prediction of Hypothesis B was not supported: myeloid
*Cirbp* fell with age. The adopted verdict is **hepatocyte-supported**
(Hypothesis A).

Reference (target) values for the cross-check derive from a prior reference
summary (`cirbp_analysis_summary.json`): age trend Spearman rho ~0.042
(p ~0.040), aged-enriched cluster ~73.1% aged with OR ~14.98, and stress-marker
fold-changes *Cdkn1a* ~5.48x, *Cirbp* ~2.03x, *Xbp1* ~2.01x, *Atf4* ~1.51x. All
cross-check metrics were labeled `reproduced` on a directional (sign / relative)
basis.

### Limitations

- **Association, not causation:** scRNA-seq supports a cellular origin and
  context for the *Cirbp* increase but does not establish causality.
- **Directional reproducibility:** absolute odds ratios and fold-changes depend
  on Leiden seed and package versions, so they are interpreted directionally; the
  local OR (8.273) and aged fraction (83.54%) differ in magnitude from the
  reference (14.98, 73.1%) while agreeing in sign and direction. *Atf4* (1.046x)
  was a weak local signal below the reference (1.51x) but kept its direction.
- **Two source h5ads:** the lineage age-trend and the subcluster/stress tables
  are computed from two different derived h5ads
  (`liver_hepatocyte_myeloid_full.h5ad` vs
  `liver_hepatocyte_myeloid_comparison.h5ad`); the source is recorded per metric.
- **Myeloid proxy:** myeloid cells are treated as a Kupffer-like immune proxy in
  the absence of finer annotation.
- **Engine opacity:** the bundled analysis engine is internally a black box; this
  is mitigated by the independent deterministic cross-check and the three-way
  comparison recorded in `results/reproduction_check.json`.
