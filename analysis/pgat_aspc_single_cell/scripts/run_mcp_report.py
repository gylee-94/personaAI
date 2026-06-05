#!/usr/bin/env python3
"""MCP-driven single-hypothesis report runner for the PGAT ASPC workflow.

This script drives the bundled MCP single-cell engine (``sc_analysis_mcp``) to
produce the cell-type expression / age-trajectory / young-old contrast /
evidence-grading tables for one hypothesis (here: gWAT VEC-niche / VEGF-axis
support of ASPC regeneration). It is run once per sex on the sex-split atlas
h5ad, writing one report tree per sex (e.g. ``results/mcp_male``).

Unlike the cross-check (which is deterministic plain scanpy and regenerates
results/), this driver needs the bundled MCP engine and the atlas h5ad:
  - MCP engine location: env ``PERSONAAI_MCP_HOME`` (defaults to
    ``personaai/scrna_mcp`` relative to the repository root).
  - Atlas data + pre-extracted gWAT h5ad: ``--aging-atlas-home`` or env
    ``AGING_ATLAS_HOME``.

The hypothesis spec is built directly from explicit parameters (no auto-parser).
Parameters default to the gWAT VEC/ASPC hypothesis but can be overridden on the
command line.

usage:
  python run_mcp_report.py \
      --aging-atlas-home /path/to/atlas \
      --h5ad gWAT_male_30k.h5ad \
      --out analysis/pgat_aspc_single_cell/results/mcp_male
"""
import argparse
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _default_mcp_home() -> str:
    # HERE is scripts/; scripts/ -> pgat_aspc_single_cell/ -> analysis/ -> repo_root
    repo_root = HERE.parents[2]  # parents: [scripts, pgat_..., analysis] -> repo_root
    return str(repo_root / "personaai" / "scrna_mcp")


def listify(v):
    return [x.strip() for x in v.replace("/", ",").split(",") if x.strip()]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--hyp-id", default="pgat_aspc_single_cell",
                    help="Hypothesis identifier used for the output report.")
    ap.add_argument("--aging-atlas-home", default=os.environ.get("AGING_ATLAS_HOME"),
                    help="Path to the Mouse Aging Atlas data + pre-extracted "
                         "gWAT h5ads (or set AGING_ATLAS_HOME).")
    ap.add_argument("--mcp-home", default=os.environ.get("PERSONAAI_MCP_HOME"),
                    help="Path to the bundled scrna_mcp engine (defaults to "
                         "personaai/scrna_mcp; or set PERSONAAI_MCP_HOME).")
    ap.add_argument("--h5ad", default="gWAT_male_30k.h5ad",
                    help="Atlas-derived h5ad filename (relative to "
                         "--aging-atlas-home) or absolute path.")
    ap.add_argument("--tissue", default="gWAT")
    ap.add_argument("--gene", default="Vegfa")
    ap.add_argument("--candidate-cell-types",
                    default="Vascular endothelial cells, "
                            "Adipoce stem and progenitor cells")
    ap.add_argument("--young-groups", default="03_months")
    ap.add_argument("--old-groups", default="23_months")
    ap.add_argument("--genotype", default="WT")
    ap.add_argument("--analysis-intent", default="lineage_screening")
    ap.add_argument("--hypothesis-text", default=None,
                    help="Optional path to a hypothesis markdown file passed to "
                         "the engine as free-text context.")
    ap.add_argument("--out", default=str(HERE.parent / "results" / "mcp_male"))
    a = ap.parse_args()

    if not a.aging_atlas_home:
        ap.error("--aging-atlas-home is required (or set AGING_ATLAS_HOME)")
    atlas_home = Path(a.aging_atlas_home).expanduser().resolve()

    mcp_home = a.mcp_home or _default_mcp_home()
    sys.path.insert(0, mcp_home)
    from sc_analysis_mcp import scrna_report_runner as R

    h5ad = Path(a.h5ad)
    if not h5ad.is_absolute():
        h5ad = atlas_home / h5ad

    text = ""
    if a.hypothesis_text:
        text = Path(a.hypothesis_text).read_text(encoding="utf-8")

    spec = R.ScrnaHypothesisSpec(
        hypothesis_id=a.hyp_id,
        tissue=a.tissue,
        gene=a.gene,
        candidate_cell_types=listify(a.candidate_cell_types),
        young_groups=listify(a.young_groups),
        old_groups=listify(a.old_groups),
        genotype=a.genotype,
        analysis_intent=a.analysis_intent,
    )

    out = a.out
    os.makedirs(out, exist_ok=True)
    res = R.run_report(spec, text, str(h5ad), out, include_mcp_plots=False)
    print("spec:", spec)
    report = Path(out) / "report.md"
    if report.exists():
        print(report.read_text(encoding="utf-8")[:1500])
    return res


if __name__ == "__main__":
    main()
