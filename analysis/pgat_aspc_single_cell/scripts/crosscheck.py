#!/usr/bin/env python3
"""Secondary PGAT directional check, separate from mouse-level manuscript models.

Age-bin Spearman trends and equally weighted age-bin expression differences
(>=16 minus <=6 months) are compared with historical reference directions.
The MCP column instead uses log2 ratios of 23/3-month expression means.
The male -1 placeholders denote expected decreases, not measured effects;
female zero placeholders cannot establish equivalence without a margin.

Both sex subsets have rho -0.7 in the archived check. This disagrees with the
historical female target +0.1. Its cause is not established by this analysis.
The output filename reproduction_check.json is retained for compatibility;
its labels do not assert numerical reproduction or biological replication.
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
VEC = "Vascular endothelial cells"
ASPC = "Adipoce stem and progenitor cells"


def _read_tsv(p):
    try:
        return pd.read_csv(p, sep="\t")
    except Exception:
        return None



def run_pgat_sex(sex, path, vec_rho_t, vec_p_t, vegfa_t, kdr_t):
    entries = []
    a = L.load_norm(path, geno="WT")
    ct_col = L.detect_celltype_col(a) or "Main_cell_type"

    # VEC proportion age trend
    try:
        _, prop = L.cell_proportion_trend(a, ct_col, AGE_COL, VEC)
        entries.append(entry(f"{sex}_VEC_rho", round(prop["rho"], 4), None, vec_rho_t,
                             L.match_label(prop["rho"], vec_rho_t, "sign"),
                             note="VEC proportion vs age (Spearman)"))
        entries.append(entry(f"{sex}_VEC_p", prop["p"], None, vec_p_t,
                             L.match_label(prop["p"], vec_p_t, "sig"),
                             note="VEC proportion trend p"))
    except Exception as ex:
        entries.append(entry(f"{sex}_VEC_rho", None, None, vec_rho_t, "not-assessable", note=str(ex)))
        entries.append(entry(f"{sex}_VEC_p", None, None, vec_p_t, "not-assessable", note=str(ex)))

    # Vegfa old-young in VEC (MCP: VEC log2fc old/young)
    mdf = _read_tsv(RESULTS_DIR / sex / "young_old_contrast.tsv")
    mcp_vegfa = None
    if mdf is not None and VEC in set(mdf.cell_type):
        mcp_vegfa = float(mdf[mdf.cell_type == VEC].log2fc_old_vs_young.iloc[0])
    vegfa = L.gene_old_minus_young(a, "Vegfa", VEC, ct_col, AGE_COL)
    entries.append(entry(f"{sex}_VEC_Vegfa_old_minus_young",
                         None if vegfa is None else round(vegfa, 5),
                         mcp_vegfa, vegfa_t,
                         L.match_label(vegfa, vegfa_t, "sign") if vegfa_t != 0 else (
                             "not-assessable"),
                         note="mean(old)-mean(young) Vegfa in VEC; mcp=VEC log2fc old/young"))

    # Kdr old-young in ASPC (MCP: not directly available -> null)
    kdr = L.gene_old_minus_young(a, "Kdr", ASPC, ct_col, AGE_COL)
    entries.append(entry(f"{sex}_ASPC_Kdr_old_minus_young",
                         None if kdr is None else round(kdr, 5),
                         None, kdr_t,
                         L.match_label(kdr, kdr_t, "sign") if kdr_t != 0 else (
                             "not-assessable"),
                         note="mean(old)-mean(young) Kdr in ASPC"))
    del a
    return entries


def run_pgat(atlas_home: Path):
    entries = []
    # target: male VEC rho -0.5 p 0.039; female rho +0.1 p 0.5
    # Vegfa: male negative, female ~0; Kdr ASPC: male negative, female ~0
    entries += run_pgat_sex("male", str(atlas_home / "gWAT_male_30k.h5ad"),
                            -0.5, 0.039, -1.0, -1.0)
    entries += run_pgat_sex("female", str(atlas_home / "gWAT_female_30k.h5ad"),
                            0.1, 0.5, 0.0, 0.0)
    return entries


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--aging-atlas-home",
        default=os.environ.get("AGING_ATLAS_HOME"),
        help="Path to the Mouse Aging Atlas data + pre-extracted gWAT h5ads "
             "(or set AGING_ATLAS_HOME).",
    )
    args = ap.parse_args()
    if not args.aging_atlas_home:
        ap.error("--aging-atlas-home is required (or set AGING_ATLAS_HOME)")
    atlas_home = Path(args.aging_atlas_home).expanduser().resolve()

    pgat = run_pgat(atlas_home)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "reproduction_check.json").write_text(
        json.dumps(pgat, indent=2, ensure_ascii=False))

    print("Directional comparison (not a numerical reproduction test):")
    print(json.dumps(pgat, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
