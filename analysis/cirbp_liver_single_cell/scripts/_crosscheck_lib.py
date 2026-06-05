"""Deterministic cross-check helpers for the CIRBP liver single-cell workflow.

These helpers recompute the key decision metrics with plain scanpy/scipy,
independently of the bundled MCP engine. They are deterministic and are used by
``crosscheck.py`` to regenerate ``results/reproduction_check.json``.

h5ad loading prefers the MCP engine's compatibility reader
(``sc_analysis_mcp.h5ad_compat.read_h5ad_compat``), which avoids IORegistryError
on older AnnData encodings. The engine location is taken from the
``PERSONAAI_MCP_HOME`` environment variable (defaulting to ``personaai/scrna_mcp``
relative to the repository root). If the compatibility reader is unavailable,
loading falls back to ``scanpy.read_h5ad``.
"""
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import scanpy as sc
from scipy.stats import spearmanr, fisher_exact


def _default_mcp_home() -> str:
    # scripts/ -> cirbp_liver_single_cell/ -> analysis/ -> repo_root
    repo_root = Path(__file__).resolve().parents[3]
    return str(repo_root / "personaai" / "scrna_mcp")


def _compat_reader():
    mcp_home = os.environ.get("PERSONAAI_MCP_HOME", _default_mcp_home())
    try:
        if mcp_home not in sys.path:
            sys.path.insert(0, mcp_home)
        from sc_analysis_mcp.h5ad_compat import read_h5ad_compat
        return read_h5ad_compat
    except Exception:
        return sc.read_h5ad


READ = _compat_reader()


def load_norm(p, geno_col="Genotype", geno=None):
    """Load an h5ad, optionally subset by genotype (e.g. WT), and CPM/log1p
    normalize if the matrix is not already log-normalized."""
    a = READ(p)
    if geno and geno_col in a.obs:
        a = a[a.obs[geno_col] == geno].copy()
    try:
        if float(a.X.max()) > 30:
            sc.pp.normalize_total(a, target_sum=1e4)
            sc.pp.log1p(a)
    except Exception:
        pass
    return a


def _v(a, g):
    """Dense 1D expression vector for gene ``g``; None if absent."""
    if g not in a.var_names:
        return None
    x = a[:, g].X
    return np.asarray(x.todense()).ravel() if hasattr(x, "todense") else np.asarray(x).ravel()


def am(s):
    """'23_months' -> 23 (age in months)."""
    return int(str(s).split("_")[0])


def detect_celltype_col(a):
    """Auto-detect the obs column whose name contains both 'cell' and 'type'."""
    for c in a.obs.columns:
        lc = c.lower()
        if "cell" in lc and "type" in lc:
            return c
    return None


def age_trend(a, g, age_col):
    x = _v(a, g)
    if x is None:
        return None
    r, p = spearmanr(a.obs[age_col].map(am).values, x)
    return dict(rho=float(r), p=float(p), pct_pos=float((x > 0).mean() * 100))


def subcluster_aged_enrichment(a, g, age_col, old, markers, max_cells=4000, res=1.0, seed=0):
    b = a.copy()
    if b.n_obs > max_cells:
        sc.pp.subsample(b, n_obs=max_cells, random_state=seed)
    sc.pp.highly_variable_genes(b, n_top_genes=min(2000, b.n_vars))
    sc.pp.pca(b, n_comps=30, random_state=seed)
    sc.pp.neighbors(b, random_state=seed)
    sc.tl.leiden(b, resolution=res, random_state=seed, flavor="igraph",
                 n_iterations=2, directed=False)
    isold = b.obs[age_col].isin(old).values
    rows = []
    for cl in b.obs.leiden.unique():
        inc = (b.obs.leiden == cl).values
        orr, p = fisher_exact([
            [int((inc & isold).sum()), int((inc & ~isold).sum())],
            [int((~inc & isold).sum()), int((~inc & ~isold).sum())],
        ])
        rows.append(dict(cluster=cl, n=int(inc.sum()),
                         aged_pct=float(b.obs.loc[inc, age_col].isin(old).mean() * 100),
                         odds_ratio=float(orr), fisher_p=float(p)))
    enr = pd.DataFrame(rows).sort_values("odds_ratio", ascending=False)
    top = enr.iloc[0].cluster
    mk = {}
    for m in markers:
        xv = _v(b, m)
        if xv is None:
            continue
        inc = (b.obs.leiden == top).values
        mk[m] = float((xv[inc].mean() + 1e-9) / (xv[~inc].mean() + 1e-9))
    return enr, top, mk


def match_label(repro, target, kind):
    if repro is None:
        return "mismatch"
    if kind == "sign":
        return "reproduced" if np.sign(repro) == np.sign(target) else "mismatch"
    if kind == "sig":
        return "reproduced" if (repro < 0.05) == (target < 0.05) else "directional-only"
    return "directional-only"
