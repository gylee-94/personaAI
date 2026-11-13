"""Figure 4E-G source data: Kdr in ASPCs and Vegfa in VECs from 3-6 months to 12 months, by sex.

Objects: gWAT_{male,female}_30k.h5ad (raw counts; 6,000 wild-type cells per age group and sex).
Per mouse: pseudobulk CPM = sum(gene UMI) / sum(UMI_count) x 1e6 within the cell type (n = 6 mice per sex at
3-6 months and 4 per sex at 12 months). OLS log2(CPM + 1) ~ period [x sex]: change within each sex and
period x sex interaction.

Manuscript: Methods, Ligand-receptor analysis. Response letter R1.4 (5), R2.5.
"""
import anndata as ad
import numpy as np
import pandas as pd
import scipy.sparse as sp
import statsmodels.formula.api as smf

from _common import ASPC, VEC, fig4_subset

rows = []
for sexf in ["male", "female"]:
    s = ad.read_h5ad(fig4_subset(sexf))
    X = s.X.tocsc() if sp.issparse(s.X) else sp.csc_matrix(s.X)
    so = s.obs.copy()
    so["ct"] = so.Main_cell_type.astype(str)
    for g in ["Vegfa", "Kdr"]:
        so[g] = np.asarray(X[:, list(s.var_names).index(g)].todense()).ravel()
    for mid, d in so.groupby("ID", observed=True):
        for g, ct, label in [("Kdr", ASPC, "Kdr in ASPCs"), ("Vegfa", VEC, "Vegfa in VECs")]:
            dd = d[d.ct == ct]
            rows.append(dict(ID=int(mid), male=float(str(d.Sex.iloc[0]) == "Male"), age=int(str(d.Age_group.iloc[0])[:2]),
                             gene=label, g=dd[g].sum(), lib=dd.UMI_count.sum()))
ex = pd.DataFrame(rows)
ex["y"] = np.log2(1e6 * ex.g / ex.lib + 1)
ex = ex[ex.age <= 12].assign(later=lambda d: (d.age == 12).astype(float))

for gene in ["Kdr in ASPCs", "Vegfa in VECs"]:
    d = ex[ex.gene == gene]
    print(f"\n== {gene}: 3-6 months -> 12 months")
    for sex, flag in [("Male", 1.0), ("Female", 0.0)]:
        m = smf.ols("y ~ later", d[d.male == flag]).fit()
        print(f"  {sex}: change {m.params['later']:+.2f} log2 CPM, P = {m.pvalues['later']:.3f}")
    m = smf.ols("y ~ later * male", d).fit()
    print(f"  period x sex interaction: P = {m.pvalues['later:male']:.3f}")
