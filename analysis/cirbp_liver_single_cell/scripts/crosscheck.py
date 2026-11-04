#!/usr/bin/env python3
"""Secondary CIRBP directional check, separate from the manuscript analysis.

Uses full-lineage h5ad for a cell-level Spearman trend and comparison h5ad
for a new cluster search (seed 0, <=4000 cells, PCA 30, Leiden resolution 1).
The enrichment contrast pools 16+23 months versus other ages, unlike the
historical reference's 23-month contrast. Marker ratios use the stored or
heuristically normalized X scale. None of these checks establishes exact
reproduction of the manual manuscript analysis or biological replication.

The historical reference is archived in ../reference/cirbp_analysis_summary.json.
The output filename reproduction_check.json is retained for compatibility;
its labels describe direction or significance categories only. P values are
saved without decimal-place rounding in new executions.
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
from comparison_labels import comparison_entry as entry

ANALYSIS_DIR = HERE.parent
RESULTS_DIR = ANALYSIS_DIR / "results"
AGE_COL = "Age_group"


def _read_tsv(p):
    try:
        return pd.read_csv(p, sep="\t")
    except Exception:
        return None



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
        entries.append(entry("age_trend_rho", None, 1.5555, 0.042, "not-assessable",
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
            entries.append(entry("subcluster", None, None, None, "not-assessable",
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
        entries.append(entry("age_trend_p", age["p"], None, 0.040,
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
                             L.match_label(orr - 1.0, 14.98 - 1.0, "sign"),
                             note=f"src={multigene_src}; ref OR=14.98"))
        ftargets = dict(Cdkn1a=5.48, Cirbp=2.03, Xbp1=2.01, Atf4=1.51)
        for g, tgt in ftargets.items():
            if g in mk:
                fc = mk[g]
                entries.append(entry(f"stress_fc_{g}", round(fc, 3), None, tgt,
                                     L.match_label(fc - 1.0, tgt - 1.0, "sign"),
                                     note=f"src={multigene_src}; fold-change top-cluster/rest"))
            else:
                entries.append(entry(f"stress_fc_{g}", None, None, tgt, "not-assessable",
                                     note="gene absent in multi-gene h5ad"))
    else:
        for m in ["top_cluster_aged_pct", "top_cluster_OR",
                  "stress_fc_Cdkn1a", "stress_fc_Cirbp", "stress_fc_Xbp1", "stress_fc_Atf4"]:
            entries.append(entry(m, None, None, None, "not-assessable",
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

    print("Directional comparison (not a numerical reproduction test):")
    print(json.dumps(cirbp, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
