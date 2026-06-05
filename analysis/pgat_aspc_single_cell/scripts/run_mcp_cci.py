#!/usr/bin/env python3
"""MCP-driven cell-cell interaction (CCI) runner for the PGAT ASPC workflow.

This script drives the bundled CCI engine (``cci_analysis_mcp``, LIANA backend)
to compare VEC->ASPC ligand-receptor signalling between young and old gWAT, per
sex, on the sex-split atlas h5ads.

``cci_compare_aging`` returns only a ``magnitude_rank``-based gained/lost summary
text (written to ``results/cci/{sex}_compare.json``); it does not return the
per-pair ``lr_means`` table. The target-pair ``lr_means`` are therefore extracted
the same way as the reference LIANA CSVs: ``li.mt.rank_aggregate`` is recomputed
on the young pool and the old pool of the same h5ad, and the three VEC->ASPC
target pairs (Lpl-Lrp1, Sparc-Fgfr1, Pdgfb-Lrp1) are read out into
``results/cci/target_pairs_compare.tsv``.

Paths are supplied via arguments / environment, never hard-coded:
  - CCI engine location: env ``PERSONAAI_MCP_HOME`` (defaults to
    ``personaai/scrna_mcp`` relative to the repository root). The engine package
    ``cci_analysis_mcp`` is expected on that path.
  - Atlas data + pre-extracted gWAT h5ads: ``--aging-atlas-home`` or env
    ``AGING_ATLAS_HOME``. h5ad filenames are overridable with ``--male-h5ad`` /
    ``--female-h5ad``.

Note: the CCI engine has its own dependency set (LIANA / scanpy); run it in the
CCI engine virtual environment.

usage:
  python run_mcp_cci.py \
      --aging-atlas-home /path/to/atlas \
      --out analysis/pgat_aspc_single_cell/results/cci
"""
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

YOUNG = ["03_months", "06_months"]
OLD = ["16_months", "23_months"]
SOURCE = "Vascular endothelial cells"
TARGET = "Adipoce stem and progenitor cells"
PAIRS = [("Lpl", "Lrp1"), ("Sparc", "Fgfr1"), ("Pdgfb", "Lrp1")]


def _default_mcp_home() -> str:
    # scripts/ -> pgat_aspc_single_cell/ -> analysis/ -> repo_root
    repo_root = HERE.parents[2]
    return str(repo_root / "personaai" / "scrna_mcp")


def lr_means_for(adata, age_groups):
    """Reference-CSV style: rank_aggregate on the age pool, read out target-pair
    lr_means for VEC->ASPC."""
    import liana as li
    sub = adata[adata.obs["Age_group"].isin(age_groups)].copy()
    sub.obs["Main_cell_type"] = sub.obs["Main_cell_type"].astype(str).astype("category")
    li.mt.rank_aggregate(sub, groupby="Main_cell_type",
                         resource_name="mouseconsensus", expr_prop=0.1,
                         verbose=False, use_raw=False)
    res = sub.uns["liana_res"]
    out = {}
    for lig, rec in PAIRS:
        m = res[(res["source"] == SOURCE) & (res["target"] == TARGET) &
                (res["ligand_complex"] == lig) & (res["receptor_complex"] == rec)]
        out[(lig, rec)] = float(m["lr_means"].iloc[0]) if len(m) else None
    return out


async def run_engine(files, out_dir):
    """Run the MCP engine cci_compare_aging per sex (single-sex h5ad each)."""
    from cci_analysis_mcp.tools import cci_tools
    for sex, p in files.items():
        args = {"adata_path": str(p), "groupby": "Main_cell_type",
                "young_groups": YOUNG, "old_groups": OLD,
                "genotype": "WT", "save_path": str(out_dir / f"cci_{sex}.png")}
        try:
            r = await cci_tools.cci_compare_aging(args)
            (out_dir / f"{sex}_compare.json").write_text(
                r if isinstance(r, str) else json.dumps(r, default=str))
            print(sex, "OK", str(r)[:600])
        except Exception as e:
            import traceback
            traceback.print_exc()
            (out_dir / f"{sex}_compare.json").write_text(
                json.dumps({"error": str(e), "args": args}))
            print(sex, "ERR", e)


def build_target_pairs(files, out_dir):
    """VEC->ASPC target-pair young/old lr_means TSV."""
    import scanpy as sc
    rows = ["sex\tligand\treceptor\tyoung_lr_means\told_lr_means\tweakened_in_old"]
    for sex, p in files.items():
        adata = sc.read_h5ad(str(p))
        adata = adata[adata.obs["Genotype"] == "WT"].copy()
        if adata.X.max() > 50:
            sc.pp.normalize_total(adata, target_sum=1e4)
            sc.pp.log1p(adata)
        y = lr_means_for(adata, YOUNG)
        o = lr_means_for(adata, OLD)
        for lig, rec in PAIRS:
            yv, ov = y[(lig, rec)], o[(lig, rec)]
            if yv is None or ov is None:
                weak = "NA"
            else:
                weak = "True" if ov < yv else "False"
            yvs = "NA" if yv is None else f"{yv:.6f}"
            ovs = "NA" if ov is None else f"{ov:.6f}"
            rows.append(f"{sex}\t{lig}\t{rec}\t{yvs}\t{ovs}\t{weak}")
            print(sex, lig, rec, "young", yvs, "old", ovs, "weakened", weak)
    (out_dir / "target_pairs_compare.tsv").write_text("\n".join(rows) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--aging-atlas-home", default=os.environ.get("AGING_ATLAS_HOME"),
                    help="Path to the Mouse Aging Atlas data + pre-extracted "
                         "gWAT h5ads (or set AGING_ATLAS_HOME).")
    ap.add_argument("--mcp-home", default=os.environ.get("PERSONAAI_MCP_HOME"),
                    help="Path to the bundled CCI engine (defaults to "
                         "personaai/scrna_mcp; or set PERSONAAI_MCP_HOME).")
    ap.add_argument("--male-h5ad", default="gWAT_male_30k.h5ad")
    ap.add_argument("--female-h5ad", default="gWAT_female_30k.h5ad")
    ap.add_argument("--out", default=str(HERE.parent / "results" / "cci"))
    a = ap.parse_args()

    if not a.aging_atlas_home:
        ap.error("--aging-atlas-home is required (or set AGING_ATLAS_HOME)")
    atlas_home = Path(a.aging_atlas_home).expanduser().resolve()

    mcp_home = a.mcp_home or _default_mcp_home()
    sys.path.insert(0, mcp_home)

    def _resolve(name):
        q = Path(name)
        return q if q.is_absolute() else atlas_home / q

    files = {"male": _resolve(a.male_h5ad), "female": _resolve(a.female_h5ad)}
    out_dir = Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    asyncio.run(run_engine(files, out_dir))
    build_target_pairs(files, out_dir)


if __name__ == "__main__":
    main()
