"""Aging Atlas scRNA-seq hypothesis report runner."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from .h5ad_compat import read_h5ad_compat
from .tools.aging_analysis import (
    sc_expression_variance,
    sc_gene_trajectory,
    sc_sex_dimorphism,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
AGING_AGENT_ROOT = PACKAGE_ROOT.parent
DEFAULT_LIVER_H5AD = (
    AGING_AGENT_ROOT
    / "Figure_data"
    / "Fig3_Cirbp_Liver"
    / "raw.data"
    / "aging_atlas_clustered.h5ad"
)
LIVER_LINEAGE_H5AD = (
    AGING_AGENT_ROOT
    / "Figure_data"
    / "Fig3_Cirbp_Liver"
    / "raw.data"
    / "liver_hepatocyte_myeloid_comparison.h5ad"
)
LIVER_FULL_LINEAGE_H5AD = (
    AGING_AGENT_ROOT
    / "Figure_data"
    / "Fig3_Cirbp_Liver"
    / "raw.data"
    / "liver_hepatocyte_myeloid_full.h5ad"
)
DEFAULT_REPORT_ROOT = AGING_AGENT_ROOT / "sc_rnaseq_reports"
AGE_ORDER = ["03_months", "06_months", "12_months", "16_months", "23_months"]
AGE_NUMERIC = {
    "03_months": 3,
    "06_months": 6,
    "12_months": 12,
    "16_months": 16,
    "23_months": 23,
}
SYMBOL_COL_CANDIDATES = (
    "Symbol",
    "symbol",
    "gene_name",
    "gene_symbol",
    "gene_symbols",
    "feature_name",
    "GeneSymbol",
)
CELL_TYPE_ALIASES = {
    "Hepatocytes": ["hepatocyte", "hepatocytes", "간세포"],
    "Myeloid cells": [
        "myeloid",
        "myeloid cells",
        "kupffer",
        "kupffer cell",
        "kupffer cells",
        "immune",
        "면역",
        "쿠퍼",
    ],
}


@dataclass(frozen=True)
class ScrnaHypothesisSpec:
    hypothesis_id: str
    tissue: str
    gene: str
    candidate_cell_types: list[str]
    young_groups: list[str]
    old_groups: list[str]
    genotype: str = "WT"
    analysis_intent: str = "lineage_screening"


@dataclass(frozen=True)
class ReportResult:
    output_dir: Path
    report_path: Path
    spec_path: Path
    feasibility_path: Path


def parse_inline_hypothesis(text: str) -> ScrnaHypothesisSpec:
    """Extract a small scRNA-seq analysis spec from inline hypothesis text."""
    tissue = _parse_tissue(text)
    gene = _parse_gene(text)
    cell_types = _parse_candidate_cell_types(text)
    analysis_intent = _parse_analysis_intent(text, cell_types)
    hypothesis_id = f"scrna_{tissue.lower()}_{gene.lower()}_origin"
    return ScrnaHypothesisSpec(
        hypothesis_id=hypothesis_id,
        tissue=tissue,
        gene=gene,
        candidate_cell_types=cell_types,
        young_groups=["03_months"],
        old_groups=["23_months"],
        analysis_intent=analysis_intent,
    )


def resolve_aging_atlas_dataset(tissue: str) -> Path:
    """Resolve the fixed Aging Atlas h5ad dataset for a tissue."""
    if tissue.lower() == "liver":
        return LIVER_LINEAGE_H5AD
    raise ValueError(f"No fixed Aging Atlas dataset configured for tissue: {tissue}")


def candidate_h5ads_for_spec(spec: ScrnaHypothesisSpec) -> list[Path]:
    """Return known Aging Atlas h5ad candidates for a parsed hypothesis spec."""
    if spec.tissue.lower() != "liver":
        return []
    if spec.analysis_intent == "hepatocyte_deep_dive":
        return [DEFAULT_LIVER_H5AD, LIVER_LINEAGE_H5AD, LIVER_FULL_LINEAGE_H5AD]
    if spec.analysis_intent == "full_lineage_screening":
        return [LIVER_FULL_LINEAGE_H5AD, LIVER_LINEAGE_H5AD, DEFAULT_LIVER_H5AD]
    return [LIVER_LINEAGE_H5AD, LIVER_FULL_LINEAGE_H5AD, DEFAULT_LIVER_H5AD]


def resolve_dataset_for_spec(
    spec: ScrnaHypothesisSpec,
    *,
    candidates: list[str | Path] | None = None,
    intent: str | None = None,
) -> dict:
    """Select the h5ad that best satisfies an inline hypothesis-derived spec."""
    effective_spec = spec
    if intent is not None and intent != spec.analysis_intent:
        effective_spec = ScrnaHypothesisSpec(
            hypothesis_id=spec.hypothesis_id,
            tissue=spec.tissue,
            gene=spec.gene,
            candidate_cell_types=spec.candidate_cell_types,
            young_groups=spec.young_groups,
            old_groups=spec.old_groups,
            genotype=spec.genotype,
            analysis_intent=intent,
        )
    candidate_paths = [Path(path) for path in (candidates or candidate_h5ads_for_spec(effective_spec))]
    if not candidate_paths:
        raise ValueError(f"No Aging Atlas h5ad candidates configured for tissue: {effective_spec.tissue}")

    scored = []
    for path in candidate_paths:
        if not path.exists():
            scored.append(
                {
                    "path": str(path),
                    "exists": False,
                    "score": -1_000_000,
                    "blocker_count": 1_000_000,
                    "blockers": [f"candidate path does not exist: {path}"],
                    "preflight": None,
                }
            )
            continue
        check = preflight_aging_atlas(path, effective_spec)
        score = _score_dataset_candidate(path, check, effective_spec)
        scored.append(
            {
                "path": str(path),
                "exists": True,
                "score": score,
                "blocker_count": len(check["blockers"]),
                "blockers": check["blockers"],
                "candidate_cell_type_counts": check["candidate_cell_type_counts"],
                "shape": check["shape"],
                "preflight": check,
            }
        )

    scored = sorted(scored, key=lambda row: row["score"], reverse=True)
    selected = scored[0]
    if not selected["exists"]:
        raise ValueError(f"No readable Aging Atlas h5ad candidate found for {effective_spec.hypothesis_id}")
    return {
        "selected_path": Path(selected["path"]),
        "selected_preflight": selected["preflight"],
        "intent": effective_spec.analysis_intent,
        "candidate_scores": scored,
    }


def inventory_aging_atlas_h5ads(root: str | Path) -> list[dict]:
    """Inspect every h5ad under an Aging Atlas root."""
    rows = []
    for h5ad_path in sorted(Path(root).rglob("*.h5ad")):
        try:
            rows.append({"path": str(h5ad_path), **inspect_aging_atlas_h5ad(h5ad_path)})
        except Exception as exc:
            rows.append(
                {
                    "path": str(h5ad_path),
                    "dataset": str(h5ad_path),
                    "read_error": str(exc),
                }
            )
    return rows


def write_inventory(rows: list[dict], output_dir: str | Path) -> tuple[Path, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "aging_atlas_h5ad_inventory.json"
    tsv_path = output_dir / "aging_atlas_h5ad_inventory.tsv"
    json_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False))
    flat_rows = []
    for row in rows:
        flat_rows.append(
            {
                "path": row.get("path", ""),
                "read_error": row.get("read_error", ""),
                "cells": row.get("shape", {}).get("cells", ""),
                "genes": row.get("shape", {}).get("genes", ""),
                "obs_columns": ",".join(row.get("obs_columns", [])),
                "var_columns": ",".join(row.get("var_columns", [])),
                "raw_present": row.get("raw_present", ""),
                "raw_n_genes": row.get("raw_n_genes", ""),
                "data_state": row.get("data_state", ""),
                "obs_index_dtype": row.get("obs_index_dtype", ""),
            }
        )
    pd.DataFrame(flat_rows).to_csv(tsv_path, sep="\t", index=False)
    return json_path, tsv_path


def run_report(
    spec: ScrnaHypothesisSpec,
    hypothesis_text: str,
    h5ad_path: str | Path | None,
    output_dir: str | Path,
    *,
    include_mcp_plots: bool = False,
    dataset_selection: dict | None = None,
) -> ReportResult:
    """Run the Aging Atlas scRNA-seq report workflow."""
    output_dir = Path(output_dir)
    results_dir = output_dir / "results"
    figures_dir = output_dir / "figures"
    results_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    if h5ad_path is None:
        dataset_selection = resolve_dataset_for_spec(spec)
        h5ad_path = dataset_selection["selected_path"]

    adata = read_h5ad_compat(str(h5ad_path))
    if spec.genotype and "Genotype" in adata.obs.columns:
        adata = adata[adata.obs["Genotype"] == spec.genotype].copy()

    feasibility = preflight_aging_atlas(Path(h5ad_path), spec, adata=adata)
    if dataset_selection is not None:
        feasibility["dataset_selection"] = _json_safe_dataset_selection(dataset_selection)
    spec = _apply_preflight_resolution(spec, feasibility)
    spec_path = output_dir / "spec.json"
    feasibility_path = output_dir / "feasibility.json"
    (output_dir / "hypothesis.md").write_text(hypothesis_text.strip() + "\n")
    spec_path.write_text(json.dumps(asdict(spec), indent=2, ensure_ascii=False))
    feasibility_path.write_text(json.dumps(feasibility, indent=2, ensure_ascii=False))

    expression_df = summarize_cell_type_expression(adata, spec)
    trajectory_df = summarize_age_trajectory(adata, spec)
    contrast_df = summarize_young_old_contrast(adata, spec)
    grading_df = grade_evidence(expression_df, contrast_df, spec, feasibility)

    expression_df.to_csv(results_dir / "cell_type_expression.tsv", sep="\t", index=False)
    trajectory_df.to_csv(results_dir / "age_trajectory.tsv", sep="\t", index=False)
    contrast_df.to_csv(results_dir / "young_old_contrast.tsv", sep="\t", index=False)
    grading_df.to_csv(results_dir / "evidence_grading.tsv", sep="\t", index=False)

    figure_rows = []
    figure_rows.append(
        _plot_cell_type_expression(
            expression_df,
            figures_dir / "F1_cell_type_expression.png",
            spec,
        )
    )
    figure_rows.append(
        _plot_age_trajectory(
            trajectory_df,
            figures_dir / "F2_age_trajectory_by_sex.png",
            spec,
        )
    )
    figure_rows.append(
        _plot_young_old_contrast(
            contrast_df,
            figures_dir / "F3_young_old_contrast.png",
            spec,
        )
    )

    if include_mcp_plots:
        figure_rows.extend(_run_mcp_plots(str(h5ad_path), figures_dir, spec))

    figure_manifest = pd.DataFrame(figure_rows)
    figure_manifest.to_csv(output_dir / "figure_manifest.tsv", sep="\t", index=False)

    report_path = output_dir / "report.md"
    report_path.write_text(
        render_report(
            spec,
            hypothesis_text,
            feasibility,
            expression_df,
            trajectory_df,
            contrast_df,
            grading_df,
            figure_manifest,
        )
    )

    return ReportResult(
        output_dir=output_dir,
        report_path=report_path,
        spec_path=spec_path,
        feasibility_path=feasibility_path,
    )


def assess_feasibility(adata, spec: ScrnaHypothesisSpec, h5ad_path: Path) -> dict:
    return preflight_aging_atlas(h5ad_path, spec, adata=adata)


def inspect_aging_atlas_h5ad(h5ad_path: str | Path, *, adata=None) -> dict:
    """Inventory an Aging Atlas h5ad schema before running analysis."""
    h5ad_path = Path(h5ad_path)
    local_adata = adata if adata is not None else read_h5ad_compat(str(h5ad_path))
    obs_summary = {}
    for column in local_adata.obs.columns:
        series = local_adata.obs[column]
        entry = {
            "dtype": str(series.dtype),
            "nunique": int(series.nunique(dropna=True)),
        }
        if 0 < entry["nunique"] <= 50:
            counts = series.dropna().astype(str).value_counts()
            entry["values"] = {str(k): int(v) for k, v in counts.items()}
        obs_summary[column] = entry

    x_dtype = str(getattr(local_adata.X, "dtype", ""))
    try:
        sample = local_adata.X[: min(1000, local_adata.n_obs)]
        if hasattr(sample, "toarray"):
            sample = sample.toarray()
        x_max = float(np.asarray(sample).max()) if local_adata.n_obs else None
    except Exception:
        x_max = None

    raw_present = local_adata.raw is not None
    raw_var_names = list(local_adata.raw.var_names) if raw_present else []
    return {
        "dataset": str(h5ad_path),
        "shape": {"cells": int(local_adata.n_obs), "genes": int(local_adata.n_vars)},
        "obs_columns": list(local_adata.obs.columns),
        "obs_summary": obs_summary,
        "var_columns": list(local_adata.var.columns),
        "raw_present": raw_present,
        "raw_n_genes": len(raw_var_names),
        "x_dtype": x_dtype,
        "x_max_sample": x_max,
        "data_state": _classify_data_state(x_dtype, x_max, local_adata.uns),
        "obs_index_dtype": str(local_adata.obs.index.dtype),
    }


def preflight_aging_atlas(
    h5ad_path: str | Path,
    spec: ScrnaHypothesisSpec,
    *,
    adata=None,
) -> dict:
    """Run deterministic Aging Atlas feasibility checks before analysis."""
    h5ad_path = Path(h5ad_path)
    local_adata = adata if adata is not None else read_h5ad_compat(str(h5ad_path))
    inventory = inspect_aging_atlas_h5ad(h5ad_path, adata=local_adata)
    required_obs = ["Age_group", "Sex", "Main_cell_type"]
    optional_obs = ["Genotype", "Sub_cell_type", "sample"]
    obs_columns = set(local_adata.obs.columns)
    present_required = [col for col in required_obs if col in obs_columns]
    missing_required = [col for col in required_obs if col not in obs_columns]
    present_optional = [col for col in optional_obs if col in obs_columns]
    gene_resolution = _resolve_gene(local_adata, spec.gene)
    cell_type_resolution = {}
    matched_cell_types = []
    if "Main_cell_type" in local_adata.obs.columns:
        available_cell_types = local_adata.obs["Main_cell_type"].dropna().astype(str)
        for cell_type in spec.candidate_cell_types:
            match = _match_cell_type(available_cell_types, cell_type)
            cell_type_resolution[cell_type] = match
            if match["matched_value"] is not None:
                matched_cell_types.append(match["matched_value"])
    else:
        available_cell_types = pd.Series(dtype=str)
        for cell_type in spec.candidate_cell_types:
            cell_type_resolution[cell_type] = {
                "kind": "miss",
                "spec_value": cell_type,
                "matched_value": None,
                "alias_source": None,
            }

    cell_type_counts = {
        cell_type: int((local_adata.obs["Main_cell_type"] == cell_type).sum())
        for cell_type in matched_cell_types
        if "Main_cell_type" in local_adata.obs.columns
    }
    blockers = []
    warnings = []
    if missing_required:
        blockers.append(f"required obs columns missing: {missing_required}")
    if gene_resolution["resolved_gene"] is None:
        blockers.append(
            f"gene not found across var_names, symbol columns, raw.var_names, and raw symbol columns: {spec.gene}"
        )
    missing_cell_types = [
        cell_type
        for cell_type, match in cell_type_resolution.items()
        if match["matched_value"] is None
    ]
    if missing_cell_types:
        blockers.append(f"candidate cell types not found: {missing_cell_types}")
    for group, count in _group_presence(local_adata, "Age_group", spec.young_groups).items():
        if count == 0:
            blockers.append(f"young group not found in Age_group: {group}")
    for group, count in _group_presence(local_adata, "Age_group", spec.old_groups).items():
        if count == 0:
            blockers.append(f"old group not found in Age_group: {group}")
    if gene_resolution["match_kind"] in {"varname_case", "symbol_case", "raw_varname_case", "raw_symbol_case"}:
        warnings.append(
            f"gene resolved by case-fold: {spec.gene} -> {gene_resolution['resolved_gene']}"
        )
    if gene_resolution["requires_raw_recovery"]:
        warnings.append(f"gene found only in raw: {spec.gene}")
    if any(match["kind"] == "alias" for match in cell_type_resolution.values()):
        warnings.append("one or more candidate cell types were resolved by alias")

    return {
        **inventory,
        "feasible": not blockers,
        "blockers": blockers,
        "warnings": warnings,
        "gene_found": gene_resolution["resolved_gene"] is not None,
        "gene_resolution": gene_resolution,
        "required_metadata_present": present_required,
        "required_metadata_missing": missing_required,
        "optional_metadata_present": present_optional,
        "cell_type_resolution": cell_type_resolution,
        "candidate_cell_type_counts": cell_type_counts,
        "young_groups_present": _group_presence(local_adata, "Age_group", spec.young_groups),
        "old_groups_present": _group_presence(local_adata, "Age_group", spec.old_groups),
    }


def summarize_cell_type_expression(adata, spec: ScrnaHypothesisSpec) -> pd.DataFrame:
    expr = _gene_expression(adata, spec.gene)
    rows = []
    for cell_type, idx in _group_indices(adata.obs["Main_cell_type"]).items():
        values = expr[idx]
        rows.append(
            {
                "cell_type": cell_type,
                "n_cells": int(values.size),
                "mean_expression": float(np.mean(values)) if values.size else 0.0,
                "median_expression": float(np.median(values)) if values.size else 0.0,
                "pct_expressing": float(np.mean(values > 0) * 100) if values.size else 0.0,
                "is_candidate": cell_type in spec.candidate_cell_types,
            }
        )
    return pd.DataFrame(rows).sort_values("mean_expression", ascending=False)


def summarize_age_trajectory(adata, spec: ScrnaHypothesisSpec) -> pd.DataFrame:
    expr = _gene_expression(adata, spec.gene)
    rows = []
    for sex in sorted(adata.obs["Sex"].dropna().unique()):
        for age in AGE_ORDER:
            mask = (adata.obs["Sex"].values == sex) & (adata.obs["Age_group"].values == age)
            values = expr[mask]
            if values.size == 0:
                continue
            rows.append(
                {
                    "sex": sex,
                    "age_group": age,
                    "age_months": AGE_NUMERIC[age],
                    "n_cells": int(values.size),
                    "mean_expression": float(np.mean(values)),
                    "pct_expressing": float(np.mean(values > 0) * 100),
                }
            )
    return pd.DataFrame(rows)


def summarize_young_old_contrast(adata, spec: ScrnaHypothesisSpec) -> pd.DataFrame:
    expr = _gene_expression(adata, spec.gene)
    rows = []
    for cell_type in spec.candidate_cell_types:
        cell_mask = adata.obs["Main_cell_type"].values == cell_type
        young_mask = cell_mask & adata.obs["Age_group"].isin(spec.young_groups).values
        old_mask = cell_mask & adata.obs["Age_group"].isin(spec.old_groups).values
        young = expr[young_mask]
        old = expr[old_mask]
        young_mean = float(np.mean(young)) if young.size else 0.0
        old_mean = float(np.mean(old)) if old.size else 0.0
        rows.append(
            {
                "cell_type": cell_type,
                "young_groups": ",".join(spec.young_groups),
                "old_groups": ",".join(spec.old_groups),
                "n_young": int(young.size),
                "n_old": int(old.size),
                "young_mean": young_mean,
                "old_mean": old_mean,
                "mean_difference": old_mean - young_mean,
                "log2fc_old_vs_young": float(
                    np.log2((old_mean + 0.01) / (young_mean + 0.01))
                ),
                "young_pct_expressing": float(np.mean(young > 0) * 100) if young.size else 0.0,
                "old_pct_expressing": float(np.mean(old > 0) * 100) if old.size else 0.0,
            }
        )
    return pd.DataFrame(rows)


def grade_evidence(
    expression_df: pd.DataFrame,
    contrast_df: pd.DataFrame,
    spec: ScrnaHypothesisSpec,
    feasibility: dict | None = None,
) -> pd.DataFrame:
    blockers = (feasibility or {}).get("blockers", [])
    candidate_expr = expression_df[expression_df["cell_type"].isin(spec.candidate_cell_types)]
    if any("candidate cell types not found" in blocker for blocker in blockers):
        verdict = "partial-celltype-comparison"
        rationale = (
            "At least one candidate cell origin was absent after dataset/genotype filtering; "
            "the observed signal can support the available cell type only, not a full origin comparison."
        )
    elif candidate_expr.empty or contrast_df.empty:
        verdict = "insufficient"
        rationale = "Candidate cell types or age contrasts were unavailable."
    else:
        top_expr = candidate_expr.sort_values("mean_expression", ascending=False).iloc[0]
        top_contrast = contrast_df.sort_values("mean_difference", ascending=False).iloc[0]
        top_expr_type = str(top_expr["cell_type"])
        top_contrast_type = str(top_contrast["cell_type"])
        if top_expr_type == "Hepatocytes" and top_contrast_type == "Hepatocytes":
            verdict = "hepatocyte-supported"
            rationale = "Hepatocytes show both dominant expression and strongest aging induction."
        elif "Myeloid" in top_expr_type or "Myeloid" in top_contrast_type:
            verdict = "immune-supported"
            rationale = "Myeloid/Kupffer-like cells show dominant expression or aging induction."
        elif float(top_contrast["mean_difference"]) > 0:
            verdict = "mixed"
            rationale = "Multiple candidate origins show age-associated signal."
        else:
            verdict = "weak"
            rationale = "Candidate cells do not show clear old-versus-young induction."
    return pd.DataFrame(
        [
            {
                "gene": spec.gene,
                "tissue": spec.tissue,
                "verdict": verdict,
                "rationale": rationale,
            }
        ]
    )


def render_report(
    spec: ScrnaHypothesisSpec,
    hypothesis_text: str,
    feasibility: dict,
    expression_df: pd.DataFrame,
    trajectory_df: pd.DataFrame,
    contrast_df: pd.DataFrame,
    grading_df: pd.DataFrame,
    figure_manifest: pd.DataFrame,
) -> str:
    verdict = str(grading_df.iloc[0]["verdict"])
    rationale = str(grading_df.iloc[0]["rationale"])
    figures = "\n".join(
        f"- {row.figure_id}: `{row.file}` — {row.caption}"
        for row in figure_manifest.itertuples(index=False)
    )
    return "\n".join(
        [
            f"# scRNA-seq Aging Atlas Report: {spec.gene} in {spec.tissue}",
            "",
            "## Inline Hypothesis",
            "",
            hypothesis_text.strip(),
            "",
            "## Parsed Specification",
            "",
            f"- hypothesis_id: `{spec.hypothesis_id}`",
            f"- tissue: `{spec.tissue}`",
            f"- gene: `{spec.gene}`",
            f"- candidate_cell_types: `{', '.join(spec.candidate_cell_types)}`",
            f"- young_groups: `{', '.join(spec.young_groups)}`",
            f"- old_groups: `{', '.join(spec.old_groups)}`",
            f"- analysis_intent: `{spec.analysis_intent}`",
            "",
            "## Feasibility Assessment",
            "",
            f"- dataset: `{feasibility['dataset']}`",
            f"- shape: `{feasibility['shape']['cells']} cells x {feasibility['shape']['genes']} genes`",
            f"- gene_found: `{feasibility['gene_found']}`",
            f"- feasible: `{feasibility.get('feasible', True)}`",
            f"- required_metadata_missing: `{', '.join(feasibility['required_metadata_missing']) or 'none'}`",
            f"- blockers: `{'; '.join(feasibility.get('blockers', [])) or 'none'}`",
            f"- warnings: `{'; '.join(feasibility.get('warnings', [])) or 'none'}`",
            f"- dataset_selection_intent: `{feasibility.get('dataset_selection', {}).get('intent', 'manual')}`",
            "",
            "## Execution Summary",
            "",
            "### Cell-Type Expression",
            "",
            _markdown_table(expression_df.head(10)),
            "",
            "### Age Trajectory",
            "",
            _markdown_table(trajectory_df.head(20)),
            "",
            "### Young-Old Contrast",
            "",
            _markdown_table(contrast_df),
            "",
            "## Sensitivity Review",
            "",
            f"- genotype_filter: `{spec.genotype}`",
            "- sex_stratification: trajectory table and figures are stratified by `Sex` when available.",
            "- annotation_limitation: Myeloid cells are treated as Kupffer-like/immune proxy unless finer annotation is available.",
            "- causal_limitation: scRNA-seq supports cellular origin and expression context, not causal inference by itself.",
            "",
            "## Evidence Grading",
            "",
            f"- verdict: `{verdict}`",
            f"- rationale: {rationale}",
            "- Hypothesis A: hepatocyte stress origin",
            "- Hypothesis B: immune/Kupffer activation origin",
            "",
            "## Figures",
            "",
            figures,
            "",
        ]
    )


def _plot_cell_type_expression(df: pd.DataFrame, path: Path, spec: ScrnaHypothesisSpec) -> dict:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    top = df.head(12).sort_values("mean_expression")
    fig, ax = plt.subplots(figsize=(7, max(3, len(top) * 0.35)))
    colors = ["#2f6f9f" if ct in spec.candidate_cell_types else "#8a8f98" for ct in top["cell_type"]]
    ax.barh(top["cell_type"], top["mean_expression"], color=colors)
    ax.set_xlabel(f"Mean {spec.gene} expression")
    ax.set_title(f"{spec.gene} expression by liver cell type")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return {
        "figure_id": "F1",
        "file": str(path),
        "analysis_step": "cell_type_expression",
        "caption": f"{spec.gene} expression by cell type.",
    }


def _plot_age_trajectory(df: pd.DataFrame, path: Path, spec: ScrnaHypothesisSpec) -> dict:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6, 4))
    for sex, group in df.groupby("sex"):
        group = group.sort_values("age_months")
        ax.plot(group["age_months"], group["mean_expression"], marker="o", label=sex)
    ax.set_xlabel("Age (months)")
    ax.set_ylabel(f"Mean {spec.gene} expression")
    ax.set_title(f"{spec.gene} age trajectory by sex")
    ax.legend()
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return {
        "figure_id": "F2",
        "file": str(path),
        "analysis_step": "age_trajectory",
        "caption": f"{spec.gene} expression trajectory across age groups by sex.",
    }


def _plot_young_old_contrast(df: pd.DataFrame, path: Path, spec: ScrnaHypothesisSpec) -> dict:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(df["cell_type"], df["mean_difference"], color="#6f8f3a")
    ax.axhline(0, color="#333333", linewidth=0.8)
    ax.set_ylabel("Old - young mean expression")
    ax.set_title(f"{spec.gene} young-old contrast by candidate origin")
    ax.tick_params(axis="x", rotation=20)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return {
        "figure_id": "F3",
        "file": str(path),
        "analysis_step": "young_old_contrast",
        "caption": f"Old-versus-young {spec.gene} contrast in candidate cell origins.",
    }


def _run_mcp_plots(h5ad_path: str, figures_dir: Path, spec: ScrnaHypothesisSpec) -> list[dict]:
    async def run_all():
        rows = []
        calls = [
            (
                "F4",
                "mcp_gene_trajectory",
                figures_dir / "F4_mcp_gene_trajectory.png",
                sc_gene_trajectory,
                {"genes": [spec.gene]},
                f"MCP-derived {spec.gene} age trajectory.",
            ),
            (
                "F5",
                "mcp_expression_variance",
                figures_dir / "F5_mcp_expression_variance.png",
                sc_expression_variance,
                {"genes": [spec.gene], "metric": "cv"},
                f"MCP-derived {spec.gene} expression variance.",
            ),
            (
                "F6",
                "mcp_sex_dimorphism",
                figures_dir / "F6_mcp_sex_dimorphism.png",
                sc_sex_dimorphism,
                {"genes": [spec.gene]},
                f"MCP-derived {spec.gene} sex dimorphism.",
            ),
        ]
        for figure_id, step, path, func, extra_args, caption in calls:
            args = {
                "adata_path": h5ad_path,
                "genotype": spec.genotype,
                "save_path": str(path),
            }
            args.update(extra_args)
            message = await func(args)
            if path.exists():
                rows.append(
                    {
                        "figure_id": figure_id,
                        "file": str(path),
                        "analysis_step": step,
                        "caption": caption,
                    }
                )
            else:
                rows.append(
                    {
                        "figure_id": figure_id,
                        "file": "",
                        "analysis_step": step,
                        "caption": f"{caption} Not generated: {message[:120]}",
                    }
                )
        return rows

    return asyncio.run(run_all())


def _parse_tissue(text: str) -> str:
    if re.search(r"\bLiver\b|간", text, re.IGNORECASE):
        return "Liver"
    return "Liver"


def _parse_gene(text: str) -> str:
    match = re.search(r"\b[A-Z][A-Z0-9]{2,}\b", text)
    if not match:
        return "Cirbp"
    symbol = match.group(0)
    return symbol[0].upper() + symbol[1:].lower()


def _parse_candidate_cell_types(text: str) -> list[str]:
    cell_types = []
    if re.search(r"hepatocyte|간세포", text, re.IGNORECASE):
        cell_types.append("Hepatocytes")
    if re.search(r"kupffer|myeloid|immune|면역|쿠퍼", text, re.IGNORECASE):
        cell_types.append("Myeloid cells")
    return cell_types or ["Hepatocytes", "Myeloid cells"]


def _parse_analysis_intent(text: str, cell_types: list[str]) -> str:
    if re.search(r"subcluster|cluster|senescence|ER stress|소포체|노화세포", text, re.IGNORECASE):
        return "hepatocyte_deep_dive"
    if re.search(r"full|전체|전수", text, re.IGNORECASE):
        return "full_lineage_screening"
    if len(cell_types) >= 2:
        return "lineage_screening"
    return "lineage_screening"


def _score_dataset_candidate(path: Path, check: dict, spec: ScrnaHypothesisSpec) -> int:
    score = 0
    score -= len(check["blockers"]) * 10_000
    if check["gene_found"]:
        score += 2_000
    matched_count = sum(
        1
        for match in check["cell_type_resolution"].values()
        if match.get("matched_value") is not None
    )
    score += matched_count * 1_000
    score += sum(min(int(count), 5_000) for count in check["candidate_cell_type_counts"].values()) // 10
    if spec.analysis_intent == "lineage_screening":
        if "comparison" in path.name:
            score += 500
        if "full" in path.name:
            score -= 200
        if "clustered" in path.name:
            score -= 500
    elif spec.analysis_intent == "full_lineage_screening":
        if "full" in path.name:
            score += 500
    elif spec.analysis_intent == "hepatocyte_deep_dive":
        if "clustered" in path.name or "categorized" in path.name:
            score += 500
    return score


def _json_safe_dataset_selection(selection: dict) -> dict:
    return {
        "selected_path": str(selection["selected_path"]),
        "intent": selection["intent"],
        "candidate_scores": [
            {
                key: value
                for key, value in row.items()
                if key != "preflight"
            }
            for row in selection["candidate_scores"]
        ],
    }


def _apply_preflight_resolution(
    spec: ScrnaHypothesisSpec,
    feasibility: dict,
) -> ScrnaHypothesisSpec:
    gene = feasibility.get("gene_resolution", {}).get("resolved_gene") or spec.gene
    matched_cell_types = []
    for cell_type in spec.candidate_cell_types:
        match = feasibility.get("cell_type_resolution", {}).get(cell_type, {})
        matched = match.get("matched_value")
        matched_cell_types.append(matched or cell_type)
    deduped_cell_types = []
    for cell_type in matched_cell_types:
        if cell_type not in deduped_cell_types:
            deduped_cell_types.append(cell_type)
    return ScrnaHypothesisSpec(
        hypothesis_id=spec.hypothesis_id,
        tissue=spec.tissue,
        gene=gene,
        candidate_cell_types=deduped_cell_types,
        young_groups=spec.young_groups,
        old_groups=spec.old_groups,
        genotype=spec.genotype,
        analysis_intent=spec.analysis_intent,
    )


def _classify_data_state(dtype_str: str, x_max: float | None, uns: dict | None) -> str:
    if uns is not None and "log1p" in uns:
        return "log_normalized"
    if "int" in dtype_str:
        return "raw_counts"
    if x_max is None:
        return "unknown"
    if x_max > 1000:
        return "raw_counts"
    if x_max < 50:
        return "log_normalized"
    return "unknown"


def _resolve_symbol_col(var_df: pd.DataFrame, target_gene: str) -> str | None:
    candidates = [col for col in SYMBOL_COL_CANDIDATES if col in var_df.columns]
    if not candidates:
        return None
    target = target_gene.casefold()
    best_col = candidates[0]
    best_hits = -1
    for col in candidates:
        values = var_df[col].dropna().astype(str).str.strip().str.casefold()
        hits = int((values == target).sum())
        if hits > best_hits:
            best_col = col
            best_hits = hits
    return best_col


def _resolve_gene_in_var(
    gene: str,
    var_names: Iterable[str],
    var_df: pd.DataFrame,
    symbol_col: str | None,
    *,
    prefix: str = "",
) -> dict | None:
    var_names_list = [str(name) for name in var_names]
    if gene in var_names_list:
        return {
            "resolved_gene": gene,
            "match_kind": f"{prefix}varname_exact",
            "symbol_col": None,
        }
    var_lower = {name.casefold(): name for name in var_names_list}
    if gene.casefold() in var_lower:
        return {
            "resolved_gene": var_lower[gene.casefold()],
            "match_kind": f"{prefix}varname_case",
            "symbol_col": None,
        }
    if symbol_col is not None and symbol_col in var_df.columns:
        values = var_df[symbol_col].dropna().astype(str).str.strip()
        if (values == gene).any():
            return {
                "resolved_gene": gene,
                "match_kind": f"{prefix}symbol_exact",
                "symbol_col": symbol_col,
            }
        value_lower = {value.casefold(): value for value in values.unique()}
        if gene.casefold() in value_lower:
            return {
                "resolved_gene": value_lower[gene.casefold()],
                "match_kind": f"{prefix}symbol_case",
                "symbol_col": symbol_col,
            }
    return None


def _resolve_gene(adata, gene: str) -> dict:
    main_symbol_col = _resolve_symbol_col(adata.var, gene)
    main_hit = _resolve_gene_in_var(gene, adata.var_names, adata.var, main_symbol_col)
    raw_symbol_col = None
    raw_hit = None
    if adata.raw is not None:
        raw_symbol_col = _resolve_symbol_col(adata.raw.var, gene)
        raw_hit = _resolve_gene_in_var(
            gene,
            adata.raw.var_names,
            adata.raw.var,
            raw_symbol_col,
            prefix="raw_",
        )
    hit = main_hit or raw_hit
    if hit is None:
        return {
            "query_gene": gene,
            "resolved_gene": None,
            "match_kind": "miss",
            "symbol_col_main": main_symbol_col,
            "symbol_col_raw": raw_symbol_col,
            "requires_raw_recovery": False,
            "requires_var_rename": False,
        }
    return {
        "query_gene": gene,
        **hit,
        "symbol_col_main": main_symbol_col,
        "symbol_col_raw": raw_symbol_col,
        "requires_raw_recovery": hit["match_kind"].startswith("raw_"),
        "requires_var_rename": "symbol" in hit["match_kind"],
    }


def _normalize_label(value: str) -> str:
    return re.sub(r"[\s_]+", " ", value).strip().casefold()


def _match_cell_type(obs_values: pd.Series, spec_value: str) -> dict:
    obs_set = set(obs_values.dropna().astype(str).unique().tolist())
    if spec_value in obs_set:
        return {
            "kind": "exact",
            "spec_value": spec_value,
            "matched_value": spec_value,
            "alias_source": None,
        }
    norm_to_obs = {_normalize_label(value): value for value in sorted(obs_set)}
    spec_norm = _normalize_label(spec_value)
    if spec_norm in norm_to_obs:
        return {
            "kind": "normalized",
            "spec_value": spec_value,
            "matched_value": norm_to_obs[spec_norm],
            "alias_source": None,
        }
    for canonical, aliases in CELL_TYPE_ALIASES.items():
        candidates = [canonical, *aliases]
        if spec_norm not in {_normalize_label(candidate) for candidate in candidates}:
            continue
        for candidate in candidates:
            if candidate in obs_set:
                return {
                    "kind": "alias",
                    "spec_value": spec_value,
                    "matched_value": candidate,
                    "alias_source": f"cell_type.{canonical}",
                }
            candidate_norm = _normalize_label(candidate)
            if candidate_norm in norm_to_obs:
                return {
                    "kind": "alias",
                    "spec_value": spec_value,
                    "matched_value": norm_to_obs[candidate_norm],
                    "alias_source": f"cell_type.{canonical}",
                }
    suggestions = obs_values.dropna().astype(str).value_counts().head(5)
    return {
        "kind": "miss",
        "spec_value": spec_value,
        "matched_value": None,
        "alias_source": None,
        "suggested_matches": {str(k): int(v) for k, v in suggestions.items()},
    }


def _gene_expression(adata, gene: str) -> np.ndarray:
    if gene not in adata.var_names:
        raise ValueError(f"Gene not found in h5ad: {gene}")
    idx = list(adata.var_names).index(gene)
    x = adata.X[:, idx]
    if hasattr(x, "toarray"):
        return np.asarray(x.toarray()).ravel()
    return np.asarray(x).ravel()


def _group_indices(values: Iterable[str]) -> dict[str, np.ndarray]:
    series = pd.Series(list(values)).reset_index(drop=True)
    positions = np.arange(series.size)
    return {str(group): positions[series == group] for group in sorted(series.dropna().unique())}


def _group_presence(adata, column: str, groups: list[str]) -> dict[str, int]:
    if column not in adata.obs.columns:
        return {group: 0 for group in groups}
    return {group: int((adata.obs[column] == group).sum()) for group in groups}


def _markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_No rows available._"
    return df.to_markdown(index=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Aging Atlas scRNA-seq hypothesis report.")
    parser.add_argument("--hypothesis-text", help="Inline hypothesis text.")
    parser.add_argument("--hypothesis-file", type=Path, help="Path to hypothesis markdown.")
    parser.add_argument("--h5ad", type=Path, help="Override h5ad path.")
    parser.add_argument("--out-dir", type=Path, help="Output directory.")
    parser.add_argument("--include-mcp-plots", action="store_true")
    parser.add_argument("--inventory-root", type=Path, help="Inspect all h5ad files under this root.")
    parser.add_argument("--inventory-out-dir", type=Path, help="Directory for inventory outputs.")
    args = parser.parse_args(argv)

    if args.inventory_root:
        out_dir = args.inventory_out_dir or (DEFAULT_REPORT_ROOT / "inventory")
        json_path, tsv_path = write_inventory(
            inventory_aging_atlas_h5ads(args.inventory_root),
            out_dir,
        )
        print(json_path)
        print(tsv_path)
        return 0

    if args.hypothesis_file:
        hypothesis_text = args.hypothesis_file.read_text()
    elif args.hypothesis_text:
        hypothesis_text = args.hypothesis_text
    else:
        raise SystemExit("--hypothesis-text or --hypothesis-file is required")

    spec = parse_inline_hypothesis(hypothesis_text)
    dataset_selection = None
    if args.h5ad:
        h5ad_path = args.h5ad
    else:
        dataset_selection = resolve_dataset_for_spec(spec)
        h5ad_path = dataset_selection["selected_path"]
    out_dir = args.out_dir or (DEFAULT_REPORT_ROOT / spec.hypothesis_id)
    result = run_report(
        spec,
        hypothesis_text,
        h5ad_path,
        out_dir,
        include_mcp_plots=args.include_mcp_plots,
        dataset_selection=dataset_selection,
    )
    print(result.report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
