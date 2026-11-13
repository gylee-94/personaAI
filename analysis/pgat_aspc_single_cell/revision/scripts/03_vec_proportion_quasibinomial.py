"""Figure 4D: VEC abundance across ages modeled from per-mouse cell counts (quasi-binomial GLM).

Reads results/gWAT_mouse_VEC_percent.csv written by 02. Binomial GLM on (VECs, other cells) per mouse with the
dispersion set to Pearson chi2 / df. Odds ratio per month within each sex; age x sex interaction across 32 mice.

Manuscript: Results, Figure 4D paragraph. Response letter R1.4 (5), R2.3.
"""
import numpy as np
import pandas as pd
import statsmodels.api as sm

from _common import RESULTS

pm = pd.read_csv(RESULTS / "gWAT_mouse_VEC_percent.csv")
pm["male"] = (pm.Sex == "Male").astype(float)


def quasi_binomial(d, cols):
    X = sm.add_constant(d[cols].astype(float))
    endog = np.column_stack([d.n_vec, d.n - d.n_vec])
    m0 = sm.GLM(endog, X, family=sm.families.Binomial()).fit()
    return sm.GLM(endog, X, family=sm.families.Binomial()).fit(scale=float(m0.pearson_chi2 / m0.df_resid))


for sex, flag in [("Male", 1.0), ("Female", 0.0)]:
    m = quasi_binomial(pm[pm.male == flag], ["age"])
    lo, hi = np.exp(m.conf_int().loc["age"])
    print(f"{sex}: odds ratio per month {np.exp(m.params['age']):.3f} (95% CI {lo:.3f}-{hi:.3f}), P = {m.pvalues['age']:.3f}")
m = quasi_binomial(pm.assign(age_male=pm.age * pm.male), ["age", "male", "age_male"])
print(f"Age x sex interaction: P = {m.pvalues['age_male']:.2f}")
