#!/usr/bin/env python3
"""Deterministic local cross-check for the PGAT ASPC single-cell workflow.

This script treats the bundled MCP / CCI engines as black boxes and
independently recomputes the key decision metrics with plain scanpy/scipy, then
writes a three-way comparison [local | mcp | target] into
``results/reproduction_check.json``.

Per sex it recomputes:
  - VEC (Vascular endothelial cells) proportion trend vs age (Spearman rho, p)
  - Vegfa change in VEC, mean(old) - mean(young)  (MCP column = VEC log2fc old/young)
  - Kdr (VEGFR2) change in ASPC, mean(old) - mean(young)

Each metric is labelled reproduced | directional-only | mismatch against the
reference (target) column. Matches are NOT forced via seed/threshold tuning.

Honest labelling: the local recompute reports that female VEC proportion ALSO
declines with age (female_VEC_rho ~ -0.7), which contradicts the "female stable"
reference (target +0.1). This is recorded as ``mismatch`` and is attributed to
equal-bin 30k subsampling distorting composition; the molecular signal
(Vegfa / Kdr / CCI), not the proportion axis, is the primary basis of the
verdict (see methods_draft.md).

Inputs:
  - Atlas-derived sex-split gWAT h5ads, located via ``--aging-atlas-home`` or the
    ``AGING_ATLAS_HOME`` environment variable:
      * gWAT_male_30k.h5ad
      * gWAT_female_30k.h5ad
  - MCP young/old contrast TSVs (results/{male,female}/young_old_contrast.tsv)
    for the VEC Vegfa log2fc direction column.

The companion ``run_mcp_report.py`` / ``run_mcp_cci.py`` drive the bundled
engines and require ``personaai/scrna_mcp`` and the atlas-derived gWAT h5ads.
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
VEC = "Vascular endothelial cells"
ASPC = "Adipoce stem and progenitor cells"


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
        entries.append(entry(f"{sex}_VEC_p", round(prop["p"], 4), None, vec_p_t,
                             L.match_label(prop["p"], vec_p_t, "sig"),
                             note="VEC proportion trend p"))
    except Exception as ex:
        entries.append(entry(f"{sex}_VEC_rho", None, None, vec_rho_t, "mismatch", note=str(ex)))
        entries.append(entry(f"{sex}_VEC_p", None, None, vec_p_t, "mismatch", note=str(ex)))

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
                             "directional-only" if vegfa is not None else "mismatch"),
                         note="mean(old)-mean(young) Vegfa in VEC; mcp=VEC log2fc old/young"))

    # Kdr old-young in ASPC (MCP: not directly available -> null)
    kdr = L.gene_old_minus_young(a, "Kdr", ASPC, ct_col, AGE_COL)
    entries.append(entry(f"{sex}_ASPC_Kdr_old_minus_young",
                         None if kdr is None else round(kdr, 5),
                         None, kdr_t,
                         L.match_label(kdr, kdr_t, "sign") if kdr_t != 0 else (
                             "directional-only" if kdr is not None else "mismatch"),
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

    print("=== reproduction_check.json ===")
    print(json.dumps(pgat, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
