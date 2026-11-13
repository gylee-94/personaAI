"""Figure 4D: VEC proportion per mouse (% of all wild-type gWAT cells of the mouse; 16 mice per sex).

Prints the VEC % of every mouse (Table R1.6a), group means by sex and age, the 12-month male versus female comparison
(unpaired Student's t-test, 4 versus 4 mice; the P = 0.039 in Figure 4D) and the per-mouse Spearman correlation with
age within each sex. Writes results/gWAT_mouse_VEC_percent.csv (per-mouse source data; read by 03).

Manuscript: Results, Figure 4D paragraph; Figure 4D legend. Response letter R1.4 (2) and (4), R1.6 (1)-(2).
"""
import pandas as pd
from scipy import stats

from _common import RESULTS, VEC, load_obs

wt = load_obs("gWAT").query("Genotype == 'WT'")
pm = wt.groupby("ID", observed=True).agg(Sex=("Sex", "first"), age=("age", "first"), n=("Main_cell_type", "size"),
                                         n_vec=("Main_cell_type", lambda x: int((x == VEC).sum())))
pm["Sex"] = pm.Sex.astype(str)
pm["vec_pct"] = 100 * pm.n_vec / pm.n

print("VEC % of every mouse (Table R1.6a):")
print(pm.sort_values("vec_pct").groupby(["Sex", "age"]).vec_pct.apply(lambda v: ", ".join(f"{x:.1f}" for x in v)).unstack().to_string())
print("\nGroup means (VEC %):")
print(pm.groupby(["Sex", "age"]).vec_pct.mean().unstack().round(1).to_string())

d12 = pm[pm.age == 12]
t = stats.ttest_ind(d12[d12.Sex == "Male"].vec_pct, d12[d12.Sex == "Female"].vec_pct)
print(f"\n12 months, male vs female (unpaired t-test, 4 vs 4 mice): P = {t.pvalue:.3f}")
for sex in ["Male", "Female"]:
    d = pm[pm.Sex == sex]
    r, p = stats.spearmanr(d.age, d.vec_pct)
    print(f"{sex}: per-mouse Spearman rho = {r:.2f}, P = {p:.3f}, n = {len(d)}")

pm.drop(columns="vec_pct").to_csv(RESULTS / "gWAT_mouse_VEC_percent.csv")
