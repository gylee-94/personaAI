# <Candidate / Tissue> Verification Report: <short title of the claim under test>

> hypothesis_id: `<hypothesis_id>`
> Hypothesis under test: <competing Hypothesis A vs Hypothesis B, with the
> prediction each makes>
> Execution mode: <single-cell: MCP-first hybrid (primary = bundled engines,
> verification = local scanpy/scipy cross-check) | human-genetics: deterministic
> Python/R scripts + sensitivity analyses>

<!--
Fill-in skeleton shared by both protocol domains. Sections 1, 2, 6, 7, 8, 9 are
common. Section content differs by domain as annotated:
  - [SINGLE-CELL] = aging-atlas single-cell report
  - [HUMAN-GENETICS] = MR / coloc report
Section "6b. Reproduction check (3-way)" is SINGLE-CELL ONLY — delete it for a
human-genetics report (human-genetics verification rests on deterministic
scripts + sensitivity analyses, not a 3-way MCP/local/reference table).
Every number must be cited from a results file and be grep-reproducible. Use
repo-relative paths only. The verdict prose is authored; the numbers are read
from the outputs.
-->

## 1. Overall Verdict

<State the verdict over the competing hypotheses (single-cell) or the candidate
(human-genetics). Then a verdict-basis table.>

| <Hypothesis / Target> | Verdict | Key reason |
|---|---|---|
| <A> | <Supported / Rejected / Partial> | <cited reason> |
| <B> | <...> | <...> |

---

## 2. Data Availability

[SINGLE-CELL] <tissue, gene(s), candidate cell types, age/sex/genotype metadata,
input h5ads, per-group cell counts; hybrid framing: MCP engines primary, local
recompute as cross-check verification.>

[HUMAN-GENETICS] <eQTL / pQTL / GWAS availability: tissue cis-eQTL evidence,
circulating pQTL availability, aging GWAS outcomes, local source files and
significance.>

---

## 3. <Cell-Type Expression (MCP)> | <pQTL Locus Manifest>

[SINGLE-CELL] Cell-type expression profile. Source: `results/cell_type_expression.tsv`.

[HUMAN-GENETICS] Lead variant / locus window / lead significance / locus variant
count per target. Source: `results/<pqtl_locus_manifest>.tsv`.

---

## 4. <Age Dynamics (MCP)> | <Lead-pQTL Wald MR>

[SINGLE-CELL] Age trajectory + young-old contrast. Source:
`results/age_trajectory.tsv`, `results/young_old_contrast.tsv`.

[HUMAN-GENETICS] Single-lead-variant Wald ratio MR (beta, SE, P) per
target/outcome, interpreted directionally. Source: `results/<mr_lead_wald>.tsv`.

---

## 5. <Subcluster / CCI> | <Colocalization>

[SINGLE-CELL] Aged-enriched subcluster phenotype, or VEC->ASPC-style
ligand-receptor strength comparison (depends on analysis_intent). Source:
`results/reproduction_check.json` / `results/cci/*`.

[HUMAN-GENETICS] Regional `coloc.abf()` PP.H3 / PP.H4 per target/outcome with
thresholds (PP.H4 > 0.8 strong, > 0.5 moderate). Source: `results/<coloc_abf>.tsv`.

---

## 6. Stage-by-Stage Verification Table

[SINGLE-CELL] 5-stage MCP-first: Feasibility, Extraction/Spec, SC analysis/report,
CCI, Cross-check, Verdict.

[HUMAN-GENETICS] instrument selection, tissue/TWAS evidence, MR, coloc/SMR,
downstream annotation.

| Stage | What ran | Tool / output | Verdict |
|---|---|---|---|
| <...> | <...> | <...> | <...> |

---

## 6b. Reproduction Check (3-way) — [SINGLE-CELL ONLY; delete for human-genetics]

Source: `results/reproduction_check.json`. MCP value, local recompute, and
reference target side by side; match label is `reproduced` / `directional-only` /
`mismatch`, reported verbatim. A `mismatch` must also appear as a section-8
limitation; it does not anchor the verdict.

| metric | MCP value | local recompute | reference target | match |
|---|---:|---:|---:|:---:|
| <metric> | <mcp> | <local> | <target> | <reproduced/directional-only/mismatch> |

---

## 7. Interpretation

[SINGLE-CELL] Read each competing hypothesis separately (A supported vs B
rejected), tied to converging evidence lines.

[HUMAN-GENETICS] Per-target interpretation tying eQTL / pQTL / MR / coloc together.

---

## 8. Conclusion

```text
<causal-chain diagram from the cited evidence>
```

### Limitations

[SINGLE-CELL] causation not proven; directional exact values (Leiden seed /
package version); subsample composition distortion; any `mismatch` disclosed
here; MCP black-box mitigated by cross-check.

[HUMAN-GENETICS] single-instrument MR; potential UK Biobank cohort overlap;
palindromic / strand-ambiguity handling; need for independent non-UKB replication.

---

## 9. Outputs

| Type | Path | Content |
|---|---|---|
| <driver / script> | `<repo-relative path>` | <...> |
| <output> | `<repo-relative path>` | <...> |
| reference provenance | see `data_manifest.tsv` | <reference source; heavy inputs not redistributed> |
