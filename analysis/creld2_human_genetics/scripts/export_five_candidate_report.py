#!/usr/bin/env python3
"""Export historical report tables; does not run MR or colocalization."""
import csv
from decimal import Decimal
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
OUT = BASE / "results/five_candidate_screen"
REPORT = OUT / "source_report_20260522.md"
TARGETS = ("FGF21", "CRELD2", "GDF15", "ADIPOQ", "SERPINE1")
OUTCOMES = ("Frailty", "GrimAge", "Telomere", "Parental longevity")


def table(text, heading):
    section = text.split(heading + "\n", 1)[1].split("\n## ", 1)[0]
    rows = [line for line in section.splitlines() if line.startswith("|")]
    return [[c.strip().strip("`") for c in line.strip("|").split("|")]
            for line in rows[2:]]


def write(name, fields, rows):
    with (OUT / name).open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def rounded_agreement(full, reported):
    """Allow the rounding precision actually present in the report."""
    report = Decimal(reported)
    return abs(Decimal(full) - report) <= Decimal(5).scaleb(report.as_tuple().exponent - 1)


def main():
    text = REPORT.read_text()
    mr = {(r[0], r[1]): r for r in table(text, "## 4. Lead pQTL Wald MR")}
    coloc = {(r[0], r[1]): r for r in table(text, "## 5. pQTL x Aging GWAS Coloc")}
    expected = {(t, o) for t in TARGETS for o in OUTCOMES}
    missing = ("ADIPOQ", "Parental longevity")
    assert set(mr) == expected - {missing}, "Unexpected MR coverage"
    assert set(coloc) == expected, "Unexpected coloc coverage"
    assert coloc[missing][2:5] == ["0", "NA", "NA"]
    rows = []
    for target in TARGETS:
        for outcome in OUTCOMES:
            key = (target, outcome)
            c = coloc[key]
            row = dict(target=target, outcome=outcome,
                       status="not_estimated_no_harmonized_overlap" if key == missing else "reported",
                       mr_beta_reported="NA", mr_se_reported="NA", mr_p_reported="NA",
                       ci95_low_approx="NA", ci95_high_approx="NA",
                       coloc_nsnps=c[2].replace(",", ""), coloc_pp_h3_reported=c[3], coloc_pp_h4_reported=c[4],
                       source="source_report_20260522.md sections 4-5")
            if key in mr:
                m = mr[key]
                beta, se = Decimal(m[2]), Decimal(m[3])
                row.update(mr_beta_reported=m[2], mr_se_reported=m[3], mr_p_reported=m[4],
                           ci95_low_approx=str(beta - Decimal("1.96") * se),
                           ci95_high_approx=str(beta + Decimal("1.96") * se))
            rows.append(row)
    # Independent published CRELD2 tables must agree at the source report's precision.
    outcome_map = {"frailty": "Frailty", "telomere": "Telomere", "parental_longevity": "Parental longevity"}
    with (BASE / "results/creld2_mr_lead_wald.tsv").open() as handle:
        for r in csv.DictReader(handle, delimiter="\t"):
            m = mr[("CRELD2", outcome_map[r["outcome"]])]
            for col, value in zip(("mr_beta", "mr_se", "mr_p"), m[2:5]):
                assert rounded_agreement(r[col], value), (col, r, value)
    with (BASE / "results/creld2_coloc_abf.tsv").open() as handle:
        for r in csv.DictReader(handle, delimiter="\t"):
            if r["analysis"] != "primary":
                continue
            c = coloc[("CRELD2", outcome_map[r["outcome"]])]
            assert int(r["nsnps"]) == int(c[2].replace(",", ""))
            assert rounded_agreement(r["PP.H3"], c[3])
            assert rounded_agreement(r["PP.H4"], c[4])
    # Recovered original all-candidate outputs must agree with every reported value.
    outcome_key = {v: k for k, v in outcome_map.items()} | {"GrimAge": "grimage"}
    with (OUT / "original_outputs/hypothesis4_mr_lead_wald.tsv").open() as handle:
        full_mr = {(r["target"], r["outcome"]): r for r in csv.DictReader(handle, delimiter="\t")}
    with (OUT / "original_outputs/hypothesis4_coloc_abf_r.tsv").open() as handle:
        full_coloc = {(r["target"], r["outcome"]): r for r in csv.DictReader(handle, delimiter="\t")}
    for target, outcome in expected:
        key = (target, outcome_key[outcome])
        c, f = coloc[(target, outcome)], full_coloc[key]
        if (target, outcome) == missing:
            assert key not in full_mr and f["status"] == "insufficient_overlap" and f["nsnps"] == "0"
            continue
        for col, value in zip(("mr_beta", "mr_se", "mr_p"), mr[(target, outcome)][2:5]):
            assert rounded_agreement(full_mr[key][col], value), (key, col, value)
        assert int(f["nsnps"]) == int(c[2].replace(",", "")), key
        assert rounded_agreement(f["PP.H3"], c[3]), key
        assert rounded_agreement(f["PP.H4"], c[4]), key
    passing =[(r["target"], r["outcome"]) for r in rows
               if r["status"] == "reported" and Decimal(r["coloc_pp_h4_reported"]) > Decimal("0.5")]
    assert passing == [("CRELD2", "Frailty")]
    assert all(Decimal(r["coloc_pp_h4_reported"]) <= Decimal("0.8")
               for r in rows if r["status"] == "reported")
    write("all_candidate_outcomes.tsv", list(rows[0]), rows)
    eqtl = []
    for r in table(text, "### 2.2 GTEx v8 eQTL"):
        for tissue, value in zip(("SAT", "VAT", "Liver"), r[1:4]):
            eqtl.append(dict(target=r[0], tissue=tissue,
                             pval_beta_reported="NA" if value == "row 없음" else value,
                             status="row_absent_in_report" if value == "row 없음" else "reported"))
    assert len(eqtl) == 15
    write("tissue_eqtl.tsv", list(eqtl[0]), eqtl)
    loci = [dict(zip(("target", "lead_variant", "locus", "lead_log10p_reported", "locus_variants"), r))
            for r in table(text, "## 3. pQTL Locus Manifest")]
    assert len(loci) == 5
    write("pqtl_loci.tsv", list(loci[0]), loci)
    print("Validated 20 combinations: 19 estimated, 1 no-overlap; 15 tissue rows; 5 loci.")
    print("All 19 estimated entries agree with the recovered original outputs at reported precision.")
    print("CRELD2 entries agree with the existing full-precision tables at reported precision.")


if __name__ == "__main__":
    main()
