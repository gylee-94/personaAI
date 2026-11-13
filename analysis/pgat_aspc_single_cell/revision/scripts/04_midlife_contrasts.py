"""Figure 4D, mid-life window of the hypothesis: VEC proportion from 3-6 months to 12 months and to 16-23 months, by sex.

All wild-type gWAT cells of each mouse (6 mice per sex at 3-6 months, 4 at 12 months, 6 at 16-23 months).
Quasi-binomial GLM on per-mouse VEC counts (dispersion = Pearson chi2 / df): change within each sex and
period x sex interaction. Reads intermediate/gWAT_obs.parquet written by 01.

Manuscript: Results, Figure 4D paragraph. Response letter R1.4 (5), R2.3.
"""
import numpy as np
import pandas as pd
import statsmodels.api as sm

from _common import VEC, load_obs

wt = load_obs("gWAT").query("Genotype == 'WT'")
per = wt.groupby("ID", observed=True).agg(Sex=("Sex", "first"), age=("age", "first"), n=("Main_cell_type", "size"),
                                          n_vec=("Main_cell_type", lambda x: int((x == VEC).sum())))
per["male"] = (per.Sex.astype(str) == "Male").astype(float)
per["vec_pct"] = 100 * per.n_vec / per.n
per["period"] = pd.cut(per.age, [0, 6, 12, 23], labels=["3-6 months", "12 months", "16-23 months"]).astype(str)


def quasi_binomial(d, cols):
    X = sm.add_constant(d[cols].astype(float))
    endog = np.column_stack([d.n_vec, d.n - d.n_vec])
    m0 = sm.GLM(endog, X, family=sm.families.Binomial()).fit()
    return sm.GLM(endog, X, family=sm.families.Binomial()).fit(scale=float(m0.pearson_chi2 / m0.df_resid))


for later in ["12 months", "16-23 months"]:
    d = per[per.period.isin(["3-6 months", later])].copy()
    d["later"] = (d.period == later).astype(float)
    d["later_male"] = d.later * d.male
    print(f"\n== 3-6 months -> {later}")
    for sex, flag in [("Male", 1.0), ("Female", 0.0)]:
        s = d[d.male == flag]
        m = quasi_binomial(s, ["later"])
        lo, hi = np.exp(m.conf_int().loc["later"])
        a, b = s[s.later == 0].vec_pct.mean(), s[s.later == 1].vec_pct.mean()
        print(f"  {sex}: {a:.1f}% -> {b:.1f}% ({100 * (b - a) / a:+.0f}%); odds ratio {np.exp(m.params['later']):.2f} "
              f"(95% CI {lo:.2f}-{hi:.2f}), P = {m.pvalues['later']:.3f}")
    m = quasi_binomial(d, ["later", "male", "later_male"])
    print(f"  period x sex interaction: P = {m.pvalues['later_male']:.3f}")
