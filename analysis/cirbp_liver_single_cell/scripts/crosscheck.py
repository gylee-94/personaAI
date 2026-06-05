#!/usr/bin/env python3
"""Deterministic local cross-check for the CIRBP liver single-cell workflow.

This script treats the bundled MCP engine as a black box and independently
recomputes the key decision metrics with plain scanpy/scipy, then writes a
three-way comparison [local | mcp | target] into ``results/reproduction_check.json``.

It is deterministic (fixed seeds) and regenerates the tracked
``results/reproduction_check.json`` next to this analysis. The companion
``run_mcp_report.py`` drives the bundled MCP engine and requires both
``personaai/scrna_mcp`` and the atlas-derived liver h5ads.

Inputs:
  - Atlas-derived liver h5ads, located via ``--aging-atlas-home`` or the
    ``AGING_ATLAS_HOME`` environment variable:
      * liver_hepatocyte_myeloid_full.h5ad        (lineage age trend)
      * liver_hepatocyte_myeloid_comparison.h5ad  (subcluster + stress markers)
  - MCP young/old contrast TSV (results/young_old_contrast.tsv) for the
    Hepatocyte log2fc direction column.

Honest labeling: matches are not forced via seed/threshold tuning. OR / fold /
aged-% absolute values differ from the reference because of Leiden seed and
package-version differences; they are interpreted directionally (sign match).
"""
import argparse
import json
import os
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _crosscheck_lib as L  # noqa: E402

ANALYSIS_DIR = HERE.parent
RESULTS_DIR = ANALYSIS_DIR / "results"
AGE_COL = "Age_group"


def _read_tsv(p):
    try:
        return pd.read_csv(p, sep="\t")
    except Exception:
        return None


def entry(metric, local, mcp, target, match, note=None):
    e = dict(metric=metric, local=local, mcp=mcp, target=target, match=match)
    if note:
        e["note"] = note
    return e


def run_cirbp(atlas_home: Path):
    entries = []
    full = atlas_home / "liver_hepatocyte_myeloid_full.h5ad"
    comparison = atlas_home / "liver_hepatocyte_myeloid_comparison.h5ad"

    # ---- age_trend: full h5ad (Hepatocytes subset). Multi-gene subcluster /
    # stress markers are not available from a single-gene full h5ad, so they use
    # the comparison h5ad.
    age = None
    multigene = None
    multigene_src = None
    loaded_for_age = None
    try:
        a = L.load_norm(str(full), geno=None)
        ct_col = L.detect_celltype_col(a) or "Main_cell_type"
        hep = a[a.obs[ct_col] == "Hepatocytes"].copy()
        age = L.age_trend(hep, "Cirbp", AGE_COL)
        loaded_for_age = "liver_hepatocyte_myeloid_full.h5ad"
        has_stress = all(g in a.var_names for g in ["Cdkn1a", "Xbp1", "Atf4"])
        if a.n_vars > 50 and has_stress:
            multigene = hep
            multigene_src = loaded_for_age
        del a
    except Exception as ex:
        entries.append(entry("age_trend_rho", None, 1.5555, 0.042, "mismatch",
                             note=f"full h5ad load failed: {ex}"))

    # multi-gene fallback (carries stress markers; same comparison h5ad as ref)
    if multigene is None:
        try:
            b = L.load_norm(str(comparison), geno=None)
            ct_col = L.detect_celltype_col(b) or "Main_cell_type"
            multigene = b[b.obs[ct_col] == "Hepatocytes"].copy()
            multigene_src = "liver_hepatocyte_myeloid_comparison.h5ad"
            if age is None:  # full failed -> age_trend from comparison
                age = L.age_trend(multigene, "Cirbp", AGE_COL)
                loaded_for_age = multigene_src
        except Exception as ex:
            multigene = None
            entries.append(entry("subcluster", None, None, None, "mismatch",
                                 note=f"multi-gene h5ad unreadable: {ex}"))

    # MCP age direction (Hepatocyte log2fc old-vs-young)
    cdf = _read_tsv(RESULTS_DIR / "young_old_contrast.tsv")
    mcp_hep_log2fc = None
    if cdf is not None and "Hepatocytes" in set(cdf.cell_type):
        mcp_hep_log2fc = float(cdf[cdf.cell_type == "Hepatocytes"].log2fc_old_vs_young.iloc[0])

    if age is not None:
        entries.append(entry("age_trend_rho", round(age["rho"], 5), mcp_hep_log2fc, 0.042,
                             L.match_label(age["rho"], 0.042, "sign"),
                             note=f"src={loaded_for_age}; mcp=hepatocyte log2fc old/young (direction)"))
        entries.append(entry("age_trend_p", round(age["p"], 5), None, 0.040,
                             L.match_label(age["p"], 0.040, "sig"),
                             note=f"src={loaded_for_age}"))

    # ---- subcluster aged enrichment + stress markers
    old = ["23_months", "16_months"]
    markers = ["Cdkn1a", "Cirbp", "Xbp1", "Atf4"]
    if multigene is not None and multigene.n_vars > 50:
        enr, top, mk = L.subcluster_aged_enrichment(
            multigene, "Cirbp", AGE_COL, old, markers)
        top_row = enr.iloc[0]
        aged_pct = float(top_row.aged_pct)
        orr = float(top_row.odds_ratio)
        # target: aged_pct 73.1% (ref cluster3) -> local vs target compared
        # around 50% (both >50% => aged-enriched direction agrees).
        # OR 14.98 -> local vs ref compared around 1.0 (sign of OR-1).
        aged_target = 73.1
        entries.append(entry("top_cluster_aged_pct", round(aged_pct, 2), None, aged_target,
                             L.match_label(aged_pct - 50.0, aged_target - 50.0, "sign"),
                             note=f"src={multigene_src}; top leiden={top}; ref cluster3=73.1%"))
        entries.append(entry("top_cluster_OR", round(orr, 3), None, 14.98,
                             L.match_label(orr - 1.0, 14.0, "sign"),
                             note=f"src={multigene_src}; ref OR=14.98"))
        ftargets = dict(Cdkn1a=5.48, Cirbp=2.03, Xbp1=2.01, Atf4=1.51)
        for g, tgt in ftargets.items():
            if g in mk:
                fc = mk[g]
                entries.append(entry(f"stress_fc_{g}", round(fc, 3), None, tgt,
                                     L.match_label(fc - 1.0, tgt - 1.0, "sign"),
                                     note=f"src={multigene_src}; fold-change top-cluster/rest"))
            else:
                entries.append(entry(f"stress_fc_{g}", None, None, tgt, "mismatch",
                                     note="gene absent in multi-gene h5ad"))
    else:
        for m in ["top_cluster_aged_pct", "top_cluster_OR",
                  "stress_fc_Cdkn1a", "stress_fc_Cirbp", "stress_fc_Xbp1", "stress_fc_Atf4"]:
            entries.append(entry(m, None, None, None, "mismatch",
                                 note="multi-gene h5ad unreadable"))

    return entries


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--aging-atlas-home",
        default=os.environ.get("AGING_ATLAS_HOME"),
        help="Path to the Mouse Aging Atlas data + pre-extracted liver h5ads "
             "(or set AGING_ATLAS_HOME).",
    )
    args = ap.parse_args()
    if not args.aging_atlas_home:
        ap.error("--aging-atlas-home is required (or set AGING_ATLAS_HOME)")
    atlas_home = Path(args.aging_atlas_home).expanduser().resolve()

    cirbp = run_cirbp(atlas_home)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "reproduction_check.json").write_text(
        json.dumps(cirbp, indent=2, ensure_ascii=False))

    print("=== reproduction_check.json ===")
    print(json.dumps(cirbp, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
