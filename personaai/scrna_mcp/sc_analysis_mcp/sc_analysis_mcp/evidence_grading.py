"""Descriptive cell-origin screening; not a test of causation or significance."""
import numpy as np
import pandas as pd


def grade_evidence(expression_df, contrast_df, spec, feasibility=None):
    blockers = (feasibility or {}).get("blockers", [])
    verdict = "insufficient"
    rationale = "Candidate cell types or valid young/old observations were unavailable."
    expr_fields = {"cell_type", "mean_expression"}
    contrast_fields = {"cell_type", "mean_difference", "n_young", "n_old"}
    if blockers or (feasibility or {}).get("feasible") is False:
        rationale = "Feasibility checks failed; no complete cell-origin comparison is supported."
        if any("candidate cell types not found" in str(b) for b in blockers):
            verdict = "partial-celltype-comparison"
    elif expr_fields.issubset(expression_df.columns) and contrast_fields.issubset(contrast_df.columns):
        candidates = set(spec.candidate_cell_types)
        expr = expression_df[expression_df.cell_type.isin(candidates)]
        contrast = contrast_df[contrast_df.cell_type.isin(candidates)]
        complete = (
            bool(candidates)
            and set(expr.cell_type) == candidates
            and set(contrast.cell_type) == candidates
            and not expr.cell_type.duplicated().any()
            and not contrast.cell_type.duplicated().any()
            and np.isfinite(expr.mean_expression).all()
            and np.isfinite(contrast[["mean_difference", "n_young", "n_old"]]).all().all()
            and (contrast.n_young > 0).all()
            and (contrast.n_old > 0).all()
        )
        if complete:
            max_change = contrast.mean_difference.max()
            if max_change <= 0:
                verdict = "weak"
                rationale = "No candidate cell type shows a positive old-minus-young mean difference."
            else:
                top_expr = set(expr.loc[expr.mean_expression == expr.mean_expression.max(), "cell_type"])
                top_change = set(contrast.loc[contrast.mean_difference == max_change, "cell_type"])
                if top_expr == top_change == {"Hepatocytes"}:
                    verdict = "hepatocyte-supported"
                    rationale = "Hepatocytes have the highest mean expression and the largest positive age contrast in this extract."
                elif top_expr == top_change and len(top_expr) == 1 and "Myeloid" in next(iter(top_expr)):
                    verdict = "immune-supported"
                    rationale = "Myeloid cells have the highest mean expression and the largest positive age contrast in this extract."
                else:
                    verdict = "mixed"
                    rationale = "A positive age contrast is present, but expression and induction do not identify a unique common origin."
    return pd.DataFrame([{
        "gene": spec.gene, "tissue": spec.tissue, "verdict": verdict,
        "rationale": rationale,
        "scope": "Descriptive extract-level screen; no mouse-level significance, power, or causal test.",
    }])
