"""Deterministic cross-check helpers for the PGAT ASPC single-cell workflow.

These helpers recompute the key decision metrics with plain scanpy/scipy,
independently of the bundled MCP / CCI engines. They are deterministic and are
used by ``crosscheck.py`` to regenerate ``results/reproduction_check.json``.

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
from scipy.stats import spearmanr


def _default_mcp_home() -> str:
    # scripts/ -> pgat_aspc_single_cell/ -> analysis/ -> repo_root
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


def cell_proportion_trend(a, ct_col, age_col, ct):
    """Per-age proportion (%) of cell type ``ct``, and its Spearman trend vs age."""
    df = a.obs.copy()
    rows = [(gv, len(d), int((d[ct_col] == ct).sum()), float((d[ct_col] == ct).mean() * 100))
            for gv, d in df.groupby(age_col)]
    t = pd.DataFrame(rows, columns=["age_group", "n_total", "n_ct", "pct"])
    t["m"] = t.age_group.map(am)
    t = t.sort_values("m")
    r, p = spearmanr(t.m, t.pct)
    return t, dict(rho=float(r), p=float(p))


def gene_old_minus_young(a, g, cell, ct_col, age_col):
    """mean(old) - mean(young) of gene ``g`` within cell type ``cell``
    (young <= 6 months, old >= 16 months)."""
    sub = a[a.obs[ct_col] == cell]
    yv = []
    ov = []
    for age in sub.obs[age_col].unique():
        x = _v(sub[sub.obs[age_col] == age], g)
        if x is None:
            return None
        (yv if am(age) <= 6 else (ov if am(age) >= 16 else [])).append(float(x.mean()))
    return (sum(ov) / len(ov) - sum(yv) / len(yv)) if yv and ov else None


def match_label(repro, target, kind):
    if repro is None:
        return "mismatch"
    if kind == "sign":
        return "reproduced" if np.sign(repro) == np.sign(target) else "mismatch"
    if kind == "sig":
        return "reproduced" if (repro < 0.05) == (target < 0.05) else "directional-only"
    return "directional-only"
