#!/usr/bin/env python3
from __future__ import annotations

import csv
import gzip
import io
import math
import tarfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "hypothesis4_followup"
OUT.mkdir(parents=True, exist_ok=True)

TARGETS = {
    "FGF21": {
        "path": ROOT / "pQTL/ukbiobank/FGF21_Q9NSA1_OID21402_v1_Oncology.tar",
        "cis_chrom": "19",
    },
    "CRELD2": {
        "path": ROOT / "pQTL/ukbiobank/CRELD2_Q6UXH1_OID20751_v1_Inflammation.tar",
        "cis_chrom": "22",
    },
    "GDF15": {
        "path": ROOT / "pQTL/ukbiobank/GDF15_Q99988_OID20251_v1_Cardiometabolic.tar",
        "cis_chrom": "19",
    },
    "ADIPOQ": {
        "path": ROOT / "pQTL/ukbiobank/ADIPOQ_Q15848_OID30748_v1_Inflammation_II.tar",
        "cis_chrom": "3",
    },
    "SERPINE1": {
        "path": ROOT / "pQTL/ukbiobank/SERPINE1_P05121_OID20342_v1_Cardiometabolic.tar",
        "cis_chrom": "7",
    },
}

OUTCOMES = {
    "frailty": ROOT / "data/aging_gwas/opengwas/metal/GCST90020053_frailty_index.metal.tsv.gz",
    "grimage": ROOT / "data/aging_gwas/opengwas/metal/GCST90014288_DNAm_GrimAge_acceleration.metal.tsv.gz",
    "telomere": ROOT / "data/aging_gwas/opengwas/metal/ieu-b-4879_telomere_length.metal.tsv.gz",
    "parental_longevity": ROOT
    / "data/aging_gwas/opengwas/metal/GCST006697_parental_longevity_combined_attained_age.metal.tsv.gz",
}


def norm_chr(chrom: str) -> str:
    return chrom.replace("chr", "").upper()


def parse_pqtl_id(vid: str) -> tuple[str, int, str, str]:
    chrom, pos, ref, alt, *_ = vid.split(":")
    return norm_chr(chrom), int(pos), ref, alt


def p_from_log10(log10p: float) -> float:
    return 0.0 if log10p > 300 else 10 ** (-log10p)


def read_pqtl(target: str, path: Path, cis_chrom: str) -> tuple[list[dict[str, object]], dict[str, object]]:
    all_rows: list[dict[str, object]] = []
    with tarfile.open(path) as tar:
        for member in tar.getmembers():
            if not member.isfile() or not member.name.endswith(".gz"):
                continue
            if f"discovery_chr{cis_chrom}_" not in member.name:
                continue
            raw = tar.extractfile(member)
            if raw is None:
                continue
            with gzip.GzipFile(fileobj=raw) as gz:
                text = io.TextIOWrapper(gz)
                reader = csv.DictReader(text, delimiter=" ")
                for row in reader:
                    chrom, id_pos, ref, alt = parse_pqtl_id(row["ID"])
                    if chrom == "X":
                        continue
                    log10p = float(row["LOG10P"])
                    all_rows.append(
                        {
                            "target": target,
                            "variant_id": row["ID"],
                            "chrom": chrom,
                            "pos": id_pos,
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
    if not all_rows:
        raise RuntimeError(f"No pQTL rows read for {target}")
    lead = max(all_rows, key=lambda r: float(r["log10p"]))
    start = int(lead["pos"]) - 500_000
    end = int(lead["pos"]) + 500_000
    locus = [
        r
        for r in all_rows
        if r["chrom"] == lead["chrom"] and start <= int(r["pos"]) <= end
    ]
    return locus, {
        "target": target,
        "lead_snp": lead["variant_id"],
        "lead_chrom": lead["chrom"],
        "lead_pos": lead["pos"],
        "lead_genpos": lead["genpos"],
        "lead_log10p": lead["log10p"],
        "locus_start": start,
        "locus_end": end,
        "total_variants": len(all_rows),
        "locus_variants": len(locus),
    }


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


def harmonize(p: dict[str, object], g: dict[str, object]) -> dict[str, object] | None:
    ea_p = str(p["effect_allele"])
    oa_p = str(p["other_allele"])
    ea_g = str(g["effect_allele"])
    oa_g = str(g["other_allele"])
    if len(ea_p) != 1 or len(oa_p) != 1 or len(ea_g) != 1 or len(oa_g) != 1:
        return None
    if {ea_p, oa_p} != {ea_g, oa_g}:
        return None
    flip = ea_p == oa_g and oa_p == ea_g
    beta_out = -float(g["beta"]) if flip else float(g["beta"])
    return {
        **{f"pqtl_{k}": v for k, v in p.items()},
        **{f"gwas_{k}": v for k, v in g.items()},
        "beta_exposure": float(p["beta"]),
        "se_exposure": float(p["se"]),
        "beta_outcome": beta_out,
        "se_outcome": float(g["se"]),
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
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    target_loci = {}
    locus_manifest = []
    for target, config in TARGETS.items():
        locus, manifest = read_pqtl(target, config["path"], str(config["cis_chrom"]))
        target_loci[target] = locus
        locus_manifest.append(manifest)

    h_fields = [
        "outcome",
        "pqtl_target",
        "pqtl_variant_id",
        "pqtl_chrom",
        "pqtl_pos",
        "pqtl_genpos",
        "pqtl_effect_allele",
        "pqtl_other_allele",
        "pqtl_eaf",
        "pqtl_beta",
        "pqtl_se",
        "pqtl_log10p",
        "pqtl_n",
        "gwas_marker",
        "gwas_beta",
        "gwas_se",
        "gwas_pval",
        "gwas_n",
        "beta_exposure",
        "se_exposure",
        "beta_outcome",
        "se_outcome",
        "harmonized_effect_allele",
        "flipped_outcome",
    ]

    summary_rows = []
    mr_rows = []
    for target, locus in target_loci.items():
        positions = {int(r["pos"]) for r in locus}
        chrom = str(locus[0]["chrom"])
        for outcome, path in OUTCOMES.items():
            gwas = read_outcome(path, chrom, positions)
            harmonized = []
            for p in locus:
                g = gwas.get(int(p["pos"]))
                if g is None:
                    continue
                h = harmonize(p, g)
                if h is not None:
                    h["outcome"] = outcome
                    harmonized.append(h)
            harmonized.sort(key=lambda r: float(r["pqtl_log10p"]), reverse=True)
            write_tsv(OUT / f"{target.lower()}_{outcome}.harmonized.tsv", harmonized, h_fields)

            strong = [r for r in harmonized if float(r["pqtl_log10p"]) > -math.log10(5e-8)]
            lead = strong[0] if strong else (harmonized[0] if harmonized else None)
            if lead:
                mr = wald(lead)
                mr_rows.append(
                    {
                        "target": target,
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
                    "target": target,
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

    write_tsv(
        OUT / "pqtl_locus_manifest.tsv",
        locus_manifest,
        [
            "target",
            "lead_snp",
            "lead_chrom",
            "lead_pos",
            "lead_genpos",
            "lead_log10p",
            "locus_start",
            "locus_end",
            "total_variants",
            "locus_variants",
        ],
    )
    write_tsv(
        OUT / "hypothesis4_mr_lead_wald.tsv",
        mr_rows,
        [
            "target",
            "outcome",
            "method",
            "snp",
            "gwas_marker",
            "pqtl_log10p",
            "beta_exposure",
            "se_exposure",
            "beta_outcome",
            "se_outcome",
            "mr_beta",
            "mr_se",
            "mr_z",
            "mr_p",
        ],
    )
    write_tsv(
        OUT / "hypothesis4_followup_summary.tsv",
        summary_rows,
        [
            "target",
            "outcome",
            "pqtl_locus_variants",
            "gwas_position_matches",
            "harmonized_snps",
            "strong_pqtl_harmonized",
            "lead_snp",
            "lead_gwas_p",
            "lead_wald_p",
        ],
    )


if __name__ == "__main__":
    main()
