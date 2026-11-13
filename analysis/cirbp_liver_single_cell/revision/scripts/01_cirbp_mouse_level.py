"""Figure 3B: age-associated Cirbp in hepatocytes and myeloid cells.

Source object: liver_hepatocyte_myeloid_full.h5ad (raw Cirbp UMI per cell; per-cell library size = obs UMI_count),
hepatocytes and myeloid cells from 50 mice.

1. Cell-level Wilcoxon rank-sum test, hepatocytes at 3 versus 23 months (unit = cell).
2. Per-mouse mean Cirbp UMI per hepatocyte: number of 23-month mice above every 3-month mouse.
3. Per-mouse pseudobulk: CPM = sum(Cirbp UMI) / sum(UMI_count) x 1e6 for each cell type and mouse;
   OLS log2(CPM + 1) ~ age (months) + sex.
Writes results/fig3b_per_mouse_pseudobulk.csv (per-mouse source data).

Manuscript: Results, Figure 3B paragraph. Response letter R1.4 (2) and (4), R2.3, R3.4.
"""
import anndata as ad
import numpy as np
import scipy.sparse as sp
import statsmodels.formula.api as smf
from scipy import stats

from _paths import RESULTS, fig3b_object

a = ad.read_h5ad(fig3b_object())
x = a.X.toarray().ravel() if sp.issparse(a.X) else np.asarray(a.X).ravel()
o = a.obs.assign(g=x)
o["ct"] = o.Main_cell_type.astype(str)
o["Age_group"] = o.Age_group.astype(str)

# 1. cell-level Wilcoxon rank-sum test
hep = o[o.ct == "Hepatocytes"]
young, old = hep[hep.Age_group == "03_months"].g, hep[hep.Age_group == "23_months"].g
print(f"Hepatocytes, 3 vs 23 months (cell-level Wilcoxon rank-sum): {len(young):,} vs {len(old):,} cells, "
      f"P = {stats.ranksums(old, young).pvalue:.2g}")

# 2. per-mouse mean Cirbp per hepatocyte
mm = hep.groupby("ID", observed=True).agg(age=("Age_group", "first"), mean_cirbp=("g", "mean"))
y3, y23 = mm[mm.age == "03_months"].mean_cirbp, mm[mm.age == "23_months"].mean_cirbp
print(f"Mean hepatocyte Cirbp: {int((y23 > y3.max()).sum())} of {len(y23)} mice at 23 months above every one of "
      f"the {len(y3)} mice at 3 months")

# 3. per-mouse pseudobulk
pb = o.groupby(["ID", "ct"], observed=True).agg(Sex=("Sex", "first"), Age_group=("Age_group", "first"),
                                                g=("g", "sum"), lib=("UMI_count", "sum"), cells=("g", "size")).reset_index()
pb["age"] = pb.Age_group.str[:2].astype(int)
pb["male"] = (pb.Sex.astype(str) == "Male").astype(float)
pb["y"] = np.log2(1e6 * pb.g / pb.lib + 1)
for ct in ["Hepatocytes", "Myeloid cells"]:
    d = pb[pb.ct == ct]
    m = smf.ols("y ~ age + male", d).fit()
    lo, hi = m.conf_int().loc["age"]
    print(f"{ct}, per-mouse pseudobulk: {m.params['age']:.3f} log2 CPM per month "
          f"(95% CI {lo:.3f} to {hi:.3f}), P = {m.pvalues['age']:.2g}, n = {len(d)} mice")

pb.drop(columns=["male", "y"]).to_csv(RESULTS / "fig3b_per_mouse_pseudobulk.csv", index=False)
