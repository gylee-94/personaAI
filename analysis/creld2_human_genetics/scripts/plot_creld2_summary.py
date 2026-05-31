#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

import matplotlib.pyplot as plt


OUTCOME_ORDER = ["frailty", "telomere", "parental_longevity"]
OUTCOME_LABELS = {
    "frailty": "Frailty",
    "telomere": "Telomere length",
    "parental_longevity": "Parental longevity",
}


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open() as f:
        return list(csv.DictReader(f, delimiter="\t"))


def neglog10(p: float) -> float:
    return -math.log10(p)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    mr = read_tsv(args.result_dir / "creld2_mr_lead_wald.tsv")
    coloc = [r for r in read_tsv(args.result_dir / "creld2_coloc_abf.tsv") if r["analysis"] == "primary"]

    eqtl = {
        "SAT": {"p": 1.85645e-12, "variant": "chr22:49,920,925"},
        "VAT": {"p": 4.96e-22, "variant": "chr22:49,917,181"},
        "Liver": {"p": 3.53306e-7, "variant": "chr22:49,923,336"},
    }

    plt.rcParams.update(
        {
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "figure.dpi": 160,
        }
    )
    fig = plt.figure(figsize=(12, 7))
    gs = fig.add_gridspec(1, 3, wspace=0.35)

    ax1 = fig.add_subplot(gs[0, 0])
    tissues = list(eqtl.keys())
    vals = [neglog10(eqtl[t]["p"]) for t in tissues]
    ax1.bar(tissues, vals, color=["#4c78a8", "#f58518", "#54a24b"])
    ax1.axhline(neglog10(5e-8), color="#8c8c8c", linestyle="--", linewidth=1)
    ax1.set_ylabel("-log10(P)")
    ax1.set_title("A. CRELD2 tissue eQTL")
    for i, tissue in enumerate(tissues):
        ax1.text(i, vals[i] + 0.5, eqtl[tissue]["variant"], ha="center", va="bottom", fontsize=8)

    ax2 = fig.add_subplot(gs[0, 1])
    mr_map = {r["outcome"]: r for r in mr}
    mr_vals = [neglog10(float(mr_map[o]["mr_p"])) for o in OUTCOME_ORDER]
    ax2.bar([OUTCOME_LABELS[o] for o in OUTCOME_ORDER], mr_vals, color="#b279a2")
    ax2.axhline(neglog10(0.05), color="#8c8c8c", linestyle="--", linewidth=1)
    ax2.set_ylabel("-log10(P)")
    ax2.set_title("B. Lead pQTL Wald MR")
    ax2.tick_params(axis="x", rotation=25)
    for i, outcome in enumerate(OUTCOME_ORDER):
        pval = float(mr_map[outcome]["mr_p"])
        beta = float(mr_map[outcome]["mr_beta"])
        ax2.text(i, mr_vals[i] + 0.05, f"P={pval:.3g}\nb={beta:.3g}", ha="center", va="bottom", fontsize=8)

    ax3 = fig.add_subplot(gs[0, 2])
    coloc_map = {r["outcome"]: r for r in coloc}
    pp4 = [float(coloc_map[o]["PP.H4"]) for o in OUTCOME_ORDER]
    y = range(len(OUTCOME_ORDER))
    ax3.barh(list(y), pp4, color="#72b7b2")
    ax3.axvline(0.5, color="#555", linestyle="--", linewidth=1)
    ax3.axvline(0.8, color="#b00020", linestyle="--", linewidth=1)
    ax3.set_yticks(list(y), [OUTCOME_LABELS[o] for o in OUTCOME_ORDER])
    ax3.set_xlim(0, 1)
    ax3.set_xlabel("PP.H4")
    ax3.set_title("C. pQTL x GWAS coloc")
    for i, val in enumerate(pp4):
        ax3.text(val + 0.015, i, f"{val:.3f}", va="center", fontsize=9)

    fig.suptitle("CRELD2 evidence summary", fontsize=14)
    png = args.out_dir / "creld2_evidence_summary.png"
    pdf = args.out_dir / "creld2_evidence_summary.pdf"
    fig.savefig(png, bbox_inches="tight")
    fig.savefig(pdf, bbox_inches="tight")
    print(png)
    print(pdf)


if __name__ == "__main__":
    main()
