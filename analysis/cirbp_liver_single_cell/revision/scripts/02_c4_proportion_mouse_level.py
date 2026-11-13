"""Figure 3D-G: cluster C4 among the sampled hepatocytes.

Source object: Cirbp_categorized_with_clusters.h5ad (2,372 hepatocytes from 49 mice, age-balanced subsample;
X log-normalized). Figure cluster labels: h5ad 'cluster' C0..C3 = figure C1..C4.

(a) C4 among hepatocytes at each age, pooled and per mouse (Table R1.5a); hepatocytes per mouse.
(b) C4 proportion at 23 months versus 3-16 months: quasi-binomial GLM on per-mouse C4 counts with sex as a covariate
    (dispersion = Pearson chi2 / df).
(c) C4 across the stored Leiden resolutions 0.3-0.7.
(d) Cirbp-positive cells (>= 1 Cirbp UMI) by cluster and UMIs per positive cell; Cdkn1a detection in C4.
(e) Detection of dissociation-associated genes by cluster (Table R3.4; van den Brink et al., Nat Methods 2017).
Writes results/fig3dg_c4_per_mouse.csv (per-mouse source data).

Manuscript: Results, Figure 3D-G paragraph; Figure 3 legend. Response letter R1.5 (1)-(3), R2.3, R3.4.
"""
import anndata as ad
import numpy as np
import pandas as pd
import statsmodels.api as sm

from _paths import RESULTS, fig3dg_object

pd.set_option("display.width", 200)
a = ad.read_h5ad(fig3dg_object())
o = a.obs.copy()
o["fig"] = o.cluster.astype(str).map({"C0": "C1", "C1": "C2", "C2": "C3", "C3": "C4"})
o["age"] = o.Age_group.astype(str).str[:2].astype(int)
o["ID"] = o.ID.astype(int)
o["male"] = (o.Sex.astype(str) == "Male").astype(float)


def detection(genes):
    X = a[:, genes].X
    X = X.toarray() if hasattr(X, "toarray") else np.asarray(X)
    return pd.DataFrame(X > 0, columns=genes).groupby(o.fig.values).mean().mul(100).round(1)


# (a)
pm = o.groupby("ID").agg(age=("age", "first"), Sex=("Sex", "first"), male=("male", "first"), cells=("fig", "size"),
                         C4=("fig", lambda v: int((v == "C4").sum()))).reset_index()
pm["C4_pct"] = (100 * pm.C4 / pm.cells).round(1)   # per-mouse %, one decimal, as in Table R1.5a
tab = pm.groupby("age").agg(hepatocytes=("cells", "sum"), mice=("ID", "size"), C4_cells=("C4", "sum"),
                            median_pct=("C4_pct", "median"), min_pct=("C4_pct", "min"), max_pct=("C4_pct", "max"))
tab["pooled_pct"] = (100 * tab.C4_cells / tab.hepatocytes).round(1)
print("== (a) C4 among hepatocytes by age (pooled and per mouse)")
print(tab.to_string())
print(f"C4 cells: {int(tab.C4_cells.sum())}; hepatocytes per mouse: {pm.cells.min()}-{pm.cells.max()}")

# (b)
d = pm.assign(old=(pm.age == 23).astype(float))
X = sm.add_constant(d[["old", "male"]])
endog = np.column_stack([d.C4, d.cells - d.C4])
m0 = sm.GLM(endog, X, family=sm.families.Binomial()).fit()
m = sm.GLM(endog, X, family=sm.families.Binomial()).fit(scale=float(m0.pearson_chi2 / m0.df_resid))
lo, hi = np.exp(m.conf_int().loc["old"])
print(f"\n== (b) C4 proportion, 23 vs 3-16 months (quasi-binomial, sex as covariate): odds ratio "
      f"{np.exp(m.params['old']):.1f} (95% CI {lo:.1f}-{hi:.1f}), P = {m.pvalues['old']:.2g}")

# (c)
print("\n== (c) C4 across Leiden resolutions")
for r in [f"leiden_r{x}" for x in ("0.3", "0.4", "0.5", "0.6", "0.7")]:
    ct = pd.crosstab(o.fig, o[r].astype(str))
    main = ct.loc["C4"].idxmax()
    print(f"  {r}: {100 * ct.loc['C4', main] / ct.loc['C4'].sum():.0f}% of C4 cells in one cluster, "
          f"which is {100 * ct.loc['C4', main] / ct[main].sum():.0f}% C4")

# (d)
gi = list(a.var_names).index("Cirbp")
x = a.X[:, gi]
x = np.asarray(x.todense()).ravel() if hasattr(x, "todense") else np.asarray(x).ravel()
umi = np.round(np.expm1(x) * o.total_counts / 1e4).astype(int)   # back-calculated from log-normalized X
pos = o[umi > 0]
print(f"\n== (d) Cirbp-positive hepatocytes: {len(pos)} of {len(o)}")
print("  by cluster:", {c: f"{int((pos.fig == c).sum())} of {int((o.fig == c).sum())}" for c in ["C1", "C2", "C3", "C4"]})
print("  Cirbp UMIs per positive cell:", pd.Series(umi[umi > 0]).value_counts().sort_index().to_dict())
print(f"  Cdkn1a detected in {detection(['Cdkn1a']).loc['C4', 'Cdkn1a']}% of C4 cells")

# (e)
DISS = ["Fos", "Atf3", "Ier2", "Hspa1b", "Junb", "Nr4a1", "Socs3", "Dusp1", "Jun", "Jund", "Egr1", "Zfp36", "Hspa8"]
print("\n== (e) % cells with detected dissociation-associated genes, by cluster")
print(detection(DISS).T.to_string())

pm.drop(columns="male").to_csv(RESULTS / "fig3dg_c4_per_mouse.csv", index=False)
