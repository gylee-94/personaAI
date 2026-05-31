#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import gzip
import io
import math
import tarfile
from pathlib import Path


OUTCOMES = {
    "frailty": "data/aging_gwas/opengwas/metal/GCST90020053_frailty_index.metal.tsv.gz",
    "telomere": "data/aging_gwas/opengwas/metal/ieu-b-4879_telomere_length.metal.tsv.gz",
    "parental_longevity": "data/aging_gwas/opengwas/metal/GCST006697_parental_longevity_combined_attained_age.metal.tsv.gz",
}


def norm_chr(chrom: str) -> str:
    return chrom.replace("chr", "").upper()


def parse_pqtl_id(variant_id: str) -> tuple[str, int, str, str]:
    chrom, pos, ref, alt, *_ = variant_id.split(":")
    return norm_chr(chrom), int(pos), ref, alt


def p_from_log10(log10p: float) -> float:
    return 0.0 if log10p > 300 else 10 ** (-log10p)


def read_creld2_pqtl(path: Path) -> tuple[list[dict[str, object]], dict[str, object]]:
    rows: list[dict[str, object]] = []
    with tarfile.open(path) as tar:
        for member in tar.getmembers():
            if not member.isfile() or not member.name.endswith(".gz"):
                continue
            if "discovery_chr22_" not in member.name:
                continue
            raw = tar.extractfile(member)
            if raw is None:
                continue
            with gzip.GzipFile(fileobj=raw) as gz:
                reader = csv.DictReader(io.TextIOWrapper(gz), delimiter=" ")
                for row in reader:
                    chrom, pos, ref, alt = parse_pqtl_id(row["ID"])
                    if chrom == "X":
                        continue
                    log10p = float(row["LOG10P"])
                    rows.append(
                        {
                            "target": "CRELD2",
                            "variant_id": row["ID"],
                            "chrom": chrom,
                            "pos": pos,
                            "ref": ref,
                            "alt": alt,
                            "genpos": int(row["GENPOS"]),
                            "effect_allele": row["ALLELE1"],
                            "other_allele": row["ALLELE0"],
                            "eaf": float(row["A1FREQ"]),
                            "beta": float(row["BETA"]),
                            "se": float(row["SE"]),
                            "log10p": log10p,
                            "pval": p_from_log10(log10p),
                            "n": int(row["N"]),
                        }
                    )
    if not rows:
        raise RuntimeError(f"No CRELD2 pQTL rows read from {path}")
    lead = max(rows, key=lambda r: float(r["log10p"]))
    start = int(lead["pos"]) - 500_000
    end = int(lead["pos"]) + 500_000
    locus = [r for r in rows if r["chrom"] == lead["chrom"] and start <= int(r["pos"]) <= end]
    manifest = {
        "target": "CRELD2",
        "lead_snp": lead["variant_id"],
        "lead_chrom": lead["chrom"],
        "lead_pos": lead["pos"],
        "lead_genpos": lead["genpos"],
        "lead_log10p": lead["log10p"],
        "locus_start": start,
        "locus_end": end,
        "total_variants": len(rows),
        "locus_variants": len(locus),
    }
    return locus, manifest


def read_outcome(path: Path, chrom: str, positions: set[int]) -> dict[int, dict[str, object]]:
    out: dict[int, dict[str, object]] = {}
    with gzip.open(path, "rt") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            if norm_chr(row["CHR"]) != chrom:
                continue
            pos = int(float(row["POS"]))
            if pos not in positions:
                continue
            out[pos] = {
                "marker": row["MARKER"],
                "effect_allele": row["EFFECT_ALLELE"],
                "other_allele": row["OTHER_ALLELE"],
                "eaf": float(row["EAF"]) if row["EAF"] not in {"", "NA"} else math.nan,
                "beta": float(row["BETA"]),
                "se": float(row["SE"]),
                "pval": float(row["PVAL"]),
                "n": int(float(row["N"])),
            }
    return out


def harmonize(pqtl: dict[str, object], gwas: dict[str, object]) -> dict[str, object] | None:
    ea_p = str(pqtl["effect_allele"])
    oa_p = str(pqtl["other_allele"])
    ea_g = str(gwas["effect_allele"])
    oa_g = str(gwas["other_allele"])
    if len(ea_p) != 1 or len(oa_p) != 1 or len(ea_g) != 1 or len(oa_g) != 1:
        return None
    if {ea_p, oa_p} != {ea_g, oa_g}:
        return None
    flip = ea_p == oa_g and oa_p == ea_g
    beta_out = -float(gwas["beta"]) if flip else float(gwas["beta"])
    return {
        **{f"pqtl_{k}": v for k, v in pqtl.items()},
        **{f"gwas_{k}": v for k, v in gwas.items()},
        "beta_exposure": float(pqtl["beta"]),
        "se_exposure": float(pqtl["se"]),
        "beta_outcome": beta_out,
        "se_outcome": float(gwas["se"]),
        "harmonized_effect_allele": ea_p,
        "flipped_outcome": flip,
    }


def wald(row: dict[str, object]) -> dict[str, float]:
    bx = float(row["beta_exposure"])
    by = float(row["beta_outcome"])
    sx = float(row["se_exposure"])
    sy = float(row["se_outcome"])
    beta = by / bx
    se = math.sqrt((sy * sy) / (bx * bx) + (by * by * sx * sx) / (bx**4))
    z = beta / se
    p = math.erfc(abs(z) / math.sqrt(2.0))
    return {"mr_beta": beta, "mr_se": se, "mr_z": z, "mr_p": p}


def write_tsv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True, help="Directory containing pQTL/ and data/")
    parser.add_argument("--out", type=Path, required=True, help="Output directory")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    pqtl_path = args.root / "pQTL/ukbiobank/CRELD2_Q6UXH1_OID20751_v1_Inflammation.tar"
    locus, manifest = read_creld2_pqtl(pqtl_path)
    write_tsv(
        args.out / "pqtl_locus_manifest.tsv",
        [manifest],
        ["target", "lead_snp", "lead_chrom", "lead_pos", "lead_genpos", "lead_log10p", "locus_start", "locus_end", "total_variants", "locus_variants"],
    )

    h_fields = [
        "outcome", "pqtl_target", "pqtl_variant_id", "pqtl_chrom", "pqtl_pos", "pqtl_genpos",
        "pqtl_effect_allele", "pqtl_other_allele", "pqtl_eaf", "pqtl_beta", "pqtl_se",
        "pqtl_log10p", "pqtl_n", "gwas_marker", "gwas_beta", "gwas_se", "gwas_pval",
        "gwas_n", "beta_exposure", "se_exposure", "beta_outcome", "se_outcome",
        "harmonized_effect_allele", "flipped_outcome",
    ]
    summary_rows: list[dict[str, object]] = []
    mr_rows: list[dict[str, object]] = []
    positions = {int(r["pos"]) for r in locus}
    chrom = str(locus[0]["chrom"])
    for outcome, rel_path in OUTCOMES.items():
        gwas = read_outcome(args.root / rel_path, chrom, positions)
        harmonized = []
        for pqtl in locus:
            g = gwas.get(int(pqtl["pos"]))
            if g is None:
                continue
            h = harmonize(pqtl, g)
            if h is not None:
                h["outcome"] = outcome
                harmonized.append(h)
        harmonized.sort(key=lambda r: float(r["pqtl_log10p"]), reverse=True)
        write_tsv(args.out / f"creld2_{outcome}.harmonized.tsv", harmonized, h_fields)
        strong = [r for r in harmonized if float(r["pqtl_log10p"]) > -math.log10(5e-8)]
        lead = strong[0] if strong else (harmonized[0] if harmonized else None)
        if lead:
            mr = wald(lead)
            mr_rows.append(
                {
                    "target": "CRELD2",
                    "outcome": outcome,
                    "method": "lead_locus_pqtl_wald",
                    "snp": lead["pqtl_variant_id"],
                    "gwas_marker": lead["gwas_marker"],
                    "pqtl_log10p": lead["pqtl_log10p"],
                    "beta_exposure": lead["beta_exposure"],
                    "se_exposure": lead["se_exposure"],
                    "beta_outcome": lead["beta_outcome"],
                    "se_outcome": lead["se_outcome"],
                    **mr,
                }
            )
        summary_rows.append(
            {
                "target": "CRELD2",
                "outcome": outcome,
                "pqtl_locus_variants": len(locus),
                "gwas_position_matches": len(gwas),
                "harmonized_snps": len(harmonized),
                "strong_pqtl_harmonized": len(strong),
                "lead_snp": lead["pqtl_variant_id"] if lead else "",
                "lead_gwas_p": lead["gwas_pval"] if lead else "",
                "lead_wald_p": mr_rows[-1]["mr_p"] if lead else "",
            }
        )

    write_tsv(args.out / "creld2_mr_lead_wald.tsv", mr_rows, list(mr_rows[0].keys()))
    write_tsv(args.out / "creld2_followup_summary.tsv", summary_rows, list(summary_rows[0].keys()))


if __name__ == "__main__":
    main()
