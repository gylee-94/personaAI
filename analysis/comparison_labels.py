"""Label only the comparison actually performed, never numerical reproduction."""
from math import isfinite


def match_label(local, reference, kind):
    if local is None or reference is None:
        return "not-assessable"
    if not isfinite(local) or not isfinite(reference):
        return "not-assessable"
    if kind == "sign":
        sign = lambda value: (value > 0) - (value < 0)
        return "directionally-concordant" if sign(float(local)) == sign(float(reference)) else "directionally-discordant"
    if kind == "sig":
        if not (0 <= local <= 1 and 0 <= reference <= 1):
            return "not-assessable"
        return "significance-category-agreement" if (local < 0.05) == (reference < 0.05) else "significance-category-disagreement"
    return "not-assessable"


def comparison_entry(metric, local, mcp, target, match, note=None):
    """Keep estimands and qualitative expectations separate from reference measurements."""
    result = dict(metric=metric, local=local, mcp=mcp, target=target, match=match,
                  comparison_scope="direction or significance category only; numerical reproduction not assessed")
    if note:
        result["note"] = note
    if metric == "age_trend_rho":
        result["local_estimand"] = "Cell-level Spearman correlation with age"
    if metric in {"top_cluster_OR", "top_cluster_aged_pct"}:
        result["design_difference"] = "Local: 16+23 months versus other ages, re-clustered. Historical reference: 23 months versus other ages, separate clustering."
    if metric == "top_cluster_aged_pct":
        result["comparison_rule"] = "Both proportions are compared with 50%; this alone is not enrichment relative to the input age composition."
    if metric.startswith("stress_fc_"):
        result["local_estimand"] = "Ratio of mean X + 1e-9 in selected cluster versus rest, on stored/normalized expression scale; not raw-count fold change"
    if "old_minus_young" in metric:
        result["local_estimand"] = "difference of equally weighted age-bin means on the stored/normalized expression scale (>=16 minus <=6 months)"
        result["reference_expectation"] = "decrease" if target == -1 else "approximately unchanged (no equivalence margin specified)"
        result["legacy_target_placeholder"] = target
        result["target"] = None
        if target == 0:
            result["match"] = "not-assessable"
    if mcp is not None:
        result["mcp_estimand"] = "log2((old mean + 0.01)/(young mean + 0.01)); 23 versus 3 months; stored expression scale"
        result["mcp_numerically_comparable_to_local"] = False
    return result
