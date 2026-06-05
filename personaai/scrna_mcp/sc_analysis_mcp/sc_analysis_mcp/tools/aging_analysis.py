"""
Aging-specific analysis tools for single-cell hypothesis validation.

Tools:
1. sc_gene_trajectory     - Gene expression trajectory across age groups (by sex)
2. sc_gene_correlation    - Gene-gene correlation analysis (by sex)
3. sc_expression_variance - Expression variance/noise changes with aging
4. sc_aging_deg           - Age-stratified DEG (Young vs Old, sex-specific)
5. sc_sex_dimorphism      - Sex-dimorphic gene expression analysis
"""
import logging
import json
from ..h5ad_compat import read_h5ad_compat

logger = logging.getLogger("sc-analysis-mcp.aging")

# ─── Constants ────────────────────────────────────────────────────────────────
AGE_ORDER = ["03_months", "06_months", "12_months", "16_months", "23_months"]
AGE_NUMERIC = {"03_months": 3, "06_months": 6, "12_months": 12, "16_months": 16, "23_months": 23}


# ─── Helper ───────────────────────────────────────────────────────────────────
def _load_and_filter(adata_path: str, genotype: str = "WT"):
    """Load h5ad and filter to WT genotype by default."""
    adata = read_h5ad_compat(adata_path)
    if genotype and "Genotype" in adata.obs.columns:
        adata = adata[adata.obs["Genotype"] == genotype].copy()
    return adata


def _get_gene_expr(adata, gene: str):
    """Extract expression vector for a gene. Returns numpy array."""
    import numpy as np
    if gene not in adata.var_names:
        return None
    idx = list(adata.var_names).index(gene)
    x = adata.X[:, idx]
    if hasattr(x, "toarray"):
        x = x.toarray().flatten()
    else:
        x = np.asarray(x).flatten()
    return x


# ═══════════════════════════════════════════════════════════════════════════════
# Tool 1: Gene Expression Trajectory
# ═══════════════════════════════════════════════════════════════════════════════
async def sc_gene_trajectory(arguments: dict) -> str:
    """
    Compute gene expression trajectory across age groups, split by sex.
    Returns mean expression ± SEM per age/sex group with trend statistics.
    """
    adata_path = arguments.get("adata_path")
    genes = arguments.get("genes", [])
    cell_type = arguments.get("cell_type", None)
    genotype = arguments.get("genotype", "WT")
    save_path = arguments.get("save_path", "/tmp/aging_gene_trajectory.png")

    if not adata_path:
        return "❌ adata_path is required"
    if not genes:
        return "❌ genes list is required (e.g. ['Cyp2e1', 'Cyp3a11'])"

    try:
        import scanpy as sc
        import numpy as np
        import pandas as pd
        from scipy import stats
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        adata = _load_and_filter(adata_path, genotype)

        if cell_type and "Main_cell_type" in adata.obs.columns:
            adata = adata[adata.obs["Main_cell_type"] == cell_type].copy()

        # Validate genes
        valid_genes = [g for g in genes if g in adata.var_names]
        missing = [g for g in genes if g not in adata.var_names]
        if not valid_genes:
            return f"❌ None of the genes found. Missing: {missing}"

        results = {}
        all_stats = []

        for gene in valid_genes:
            expr = _get_gene_expr(adata, gene)
            df = pd.DataFrame({
                "expr": expr,
                "Age_group": adata.obs["Age_group"].values,
                "Sex": adata.obs["Sex"].values
            })

            gene_result = {}
            for sex in ["Male", "Female"]:
                sex_df = df[df["Sex"] == sex]
                trajectory = []
                for age in AGE_ORDER:
                    age_vals = sex_df[sex_df["Age_group"] == age]["expr"]
                    if len(age_vals) > 0:
                        trajectory.append({
                            "age": age,
                            "mean": float(np.mean(age_vals)),
                            "sem": float(stats.sem(age_vals)) if len(age_vals) > 1 else 0.0,
                            "n_cells": int(len(age_vals)),
                            "pct_expressing": float((age_vals > 0).mean() * 100)
                        })

                # Trend test (Spearman correlation with numeric age)
                if len(trajectory) >= 3:
                    ages_num = [AGE_NUMERIC[t["age"]] for t in trajectory]
                    means = [t["mean"] for t in trajectory]
                    rho, pval = stats.spearmanr(ages_num, means)
                    trend = {"spearman_rho": round(rho, 4), "p_value": round(pval, 6),
                             "direction": "↑ increasing" if rho > 0.3 else "↓ decreasing" if rho < -0.3 else "→ stable"}
                else:
                    trend = {"spearman_rho": None, "p_value": None, "direction": "insufficient data"}

                gene_result[sex] = {"trajectory": trajectory, "trend": trend}

            results[gene] = gene_result

            # Collect for summary
            for sex in ["Male", "Female"]:
                t = gene_result[sex]["trend"]
                all_stats.append(f"   {gene} ({sex}): rho={t['spearman_rho']}, p={t['p_value']} {t['direction']}")

        # ── Plot ──
        n_genes = len(valid_genes)
        fig, axes = plt.subplots(1, n_genes, figsize=(5 * n_genes, 4), squeeze=False)

        for i, gene in enumerate(valid_genes):
            ax = axes[0, i]
            for sex, color in [("Male", "#4393C3"), ("Female", "#D6604D")]:
                traj = results[gene][sex]["trajectory"]
                if traj:
                    x = [AGE_NUMERIC[t["age"]] for t in traj]
                    y = [t["mean"] for t in traj]
                    yerr = [t["sem"] for t in traj]
                    ax.errorbar(x, y, yerr=yerr, marker="o", label=sex, color=color, capsize=3, linewidth=2)
            ax.set_title(gene, fontsize=13, fontweight="bold")
            ax.set_xlabel("Age (months)")
            ax.set_ylabel("Mean Expression")
            ax.set_xticks([3, 6, 12, 16, 23])
            ax.legend()
            ax.grid(alpha=0.3)

        plt.suptitle(f"Gene Expression Trajectory (Genotype={genotype})", fontsize=14, fontweight="bold")
        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        plt.close()

        # ── Summary ──
        missing_str = f"\n⚠️ Missing genes: {missing}" if missing else ""
        stats_str = "\n".join(all_stats)

        return f"""📈 Gene Expression Trajectory Complete!

📊 Genes analyzed: {valid_genes}{missing_str}
🧬 Cells: {adata.n_obs} ({genotype})

🔬 Trend Analysis (Spearman):
{stats_str}

💾 Plot: {save_path}
📋 JSON data available for downstream analysis

🎯 Next: sc_gene_correlation to test co-expression patterns"""

    except Exception as e:
        logger.error(f"Gene trajectory error: {e}", exc_info=True)
        return f"❌ {e}"


# ═══════════════════════════════════════════════════════════════════════════════
# Tool 2: Gene-Gene Correlation
# ═══════════════════════════════════════════════════════════════════════════════
async def sc_gene_correlation(arguments: dict) -> str:
    """
    Compute gene-gene correlations stratified by sex and/or age group.
    Tests whether two genes are co-regulated differently by sex during aging.
    """
    adata_path = arguments.get("adata_path")
    gene_pairs = arguments.get("gene_pairs", [])
    stratify_by = arguments.get("stratify_by", "Sex")
    genotype = arguments.get("genotype", "WT")
    cell_type = arguments.get("cell_type", None)
    save_path = arguments.get("save_path", "/tmp/aging_gene_correlation.png")

    if not adata_path:
        return "❌ adata_path is required"
    if not gene_pairs:
        return "❌ gene_pairs required. e.g. [['Cyp2e1','Srd5a1'], ['Col1a1','Tgfb1']]"

    try:
        import numpy as np
        import pandas as pd
        from scipy import stats
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        adata = _load_and_filter(adata_path, genotype)
        if cell_type and "Main_cell_type" in adata.obs.columns:
            adata = adata[adata.obs["Main_cell_type"] == cell_type].copy()

        results = []
        n_pairs = len(gene_pairs)
        fig, axes = plt.subplots(1, n_pairs, figsize=(6 * n_pairs, 5), squeeze=False)

        for idx, pair in enumerate(gene_pairs):
            gene_a, gene_b = pair[0], pair[1]
            expr_a = _get_gene_expr(adata, gene_a)
            expr_b = _get_gene_expr(adata, gene_b)

            if expr_a is None or expr_b is None:
                missing = gene_a if expr_a is None else gene_b
                results.append(f"   {gene_a} vs {gene_b}: ❌ '{missing}' not found")
                continue

            ax = axes[0, idx]
            pair_results = []

            if stratify_by == "Sex":
                groups = {"Male": "#4393C3", "Female": "#D6604D"}
            elif stratify_by == "Age_group":
                groups = {a: None for a in AGE_ORDER}
            else:
                groups = {"All": "#333333"}

            for grp, color in groups.items():
                if stratify_by == "All":
                    mask = np.ones(len(adata), dtype=bool)
                else:
                    mask = adata.obs[stratify_by].values == grp

                a_vals = expr_a[mask]
                b_vals = expr_b[mask]

                if len(a_vals) < 5:
                    continue

                r, p = stats.spearmanr(a_vals, b_vals)
                pair_results.append(f"      {grp}: r={r:.3f}, p={p:.2e}, n={len(a_vals)}")

                ax.scatter(a_vals, b_vals, alpha=0.4, s=15, label=f"{grp} (r={r:.2f})", color=color)

            ax.set_xlabel(gene_a)
            ax.set_ylabel(gene_b)
            ax.set_title(f"{gene_a} vs {gene_b}", fontweight="bold")
            ax.legend(fontsize=8)
            ax.grid(alpha=0.3)

            results.append(f"   {gene_a} vs {gene_b}:\n" + "\n".join(pair_results))

        plt.suptitle(f"Gene Correlations (stratified by {stratify_by})", fontsize=13, fontweight="bold")
        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        plt.close()

        results_str = "\n".join(results)
        return f"""🔗 Gene Correlation Analysis Complete!

📊 Stratified by: {stratify_by}
🧬 Cells: {adata.n_obs} ({genotype})

🔬 Results (Spearman):
{results_str}

💾 Plot: {save_path}
🎯 Next: sc_expression_variance to check expression noise changes"""

    except Exception as e:
        logger.error(f"Gene correlation error: {e}", exc_info=True)
        return f"❌ {e}"


# ═══════════════════════════════════════════════════════════════════════════════
# Tool 3: Expression Variance (Transcriptional Noise)
# ═══════════════════════════════════════════════════════════════════════════════
async def sc_expression_variance(arguments: dict) -> str:
    """
    Analyze expression variance (transcriptional noise) changes with aging.
    Computes CV (coefficient of variation) and Fano factor per age/sex group.
    Increased variance = loss of transcriptional control during aging.
    """
    adata_path = arguments.get("adata_path")
    genes = arguments.get("genes", [])
    genotype = arguments.get("genotype", "WT")
    cell_type = arguments.get("cell_type", None)
    metric = arguments.get("metric", "cv")  # "cv" or "fano"
    save_path = arguments.get("save_path", "/tmp/aging_expression_variance.png")

    if not adata_path:
        return "❌ adata_path is required"
    if not genes:
        return "❌ genes list is required"

    try:
        import numpy as np
        import pandas as pd
        from scipy import stats
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        adata = _load_and_filter(adata_path, genotype)
        if cell_type and "Main_cell_type" in adata.obs.columns:
            adata = adata[adata.obs["Main_cell_type"] == cell_type].copy()

        valid_genes = [g for g in genes if g in adata.var_names]
        if not valid_genes:
            return f"❌ None of the genes found in data"

        records = []
        for gene in valid_genes:
            expr = _get_gene_expr(adata, gene)
            for sex in ["Male", "Female"]:
                for age in AGE_ORDER:
                    mask = (adata.obs["Sex"].values == sex) & (adata.obs["Age_group"].values == age)
                    vals = expr[mask]
                    if len(vals) < 3:
                        continue
                    mean_val = np.mean(vals)
                    std_val = np.std(vals)
                    cv = std_val / mean_val if mean_val > 0 else 0
                    fano = (std_val ** 2) / mean_val if mean_val > 0 else 0
                    records.append({
                        "gene": gene, "sex": sex, "age": age,
                        "age_num": AGE_NUMERIC[age],
                        "mean": mean_val, "std": std_val,
                        "cv": cv, "fano": fano,
                        "n_cells": int(mask.sum())
                    })

        if not records:
            return "❌ Not enough cells per group to compute variance"

        df = pd.DataFrame(records)
        metric_col = metric  # "cv" or "fano"
        metric_label = "CV (Coefficient of Variation)" if metric == "cv" else "Fano Factor"

        # ── Plot ──
        n_genes = len(valid_genes)
        fig, axes = plt.subplots(1, n_genes, figsize=(5 * n_genes, 4), squeeze=False)

        summary_lines = []
        for i, gene in enumerate(valid_genes):
            ax = axes[0, i]
            for sex, color in [("Male", "#4393C3"), ("Female", "#D6604D")]:
                gdf = df[(df["gene"] == gene) & (df["sex"] == sex)].sort_values("age_num")
                if len(gdf) >= 2:
                    ax.plot(gdf["age_num"], gdf[metric_col], "o-", color=color, label=sex, linewidth=2)
                    # Trend
                    if len(gdf) >= 3:
                        rho, pval = stats.spearmanr(gdf["age_num"], gdf[metric_col])
                        direction = "↑" if rho > 0.3 else "↓" if rho < -0.3 else "→"
                        summary_lines.append(f"   {gene} ({sex}): {direction} rho={rho:.3f}, p={pval:.4f}")

            ax.set_title(gene, fontweight="bold")
            ax.set_xlabel("Age (months)")
            ax.set_ylabel(metric_label)
            ax.set_xticks([3, 6, 12, 16, 23])
            ax.legend()
            ax.grid(alpha=0.3)

        plt.suptitle(f"Expression Variance Trajectory ({metric_label})", fontsize=13, fontweight="bold")
        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        plt.close()

        summary_str = "\n".join(summary_lines) if summary_lines else "   Insufficient data for trend test"

        return f"""📊 Expression Variance Analysis Complete!

📈 Metric: {metric_label}
🧬 Genes: {valid_genes}
👥 Cells: {adata.n_obs} ({genotype})

🔬 Variance Trend (Spearman):
{summary_str}

💡 Interpretation:
   ↑ Increasing variance = loss of transcriptional control with aging
   Sex differences in variance = sex-specific regulatory breakdown

💾 Plot: {save_path}
🎯 Next: sc_aging_deg for formal Young vs Old DEG testing"""

    except Exception as e:
        logger.error(f"Expression variance error: {e}", exc_info=True)
        return f"❌ {e}"


# ═══════════════════════════════════════════════════════════════════════════════
# Tool 4: Aging DEG (Young vs Old, sex-stratified)
# ═══════════════════════════════════════════════════════════════════════════════
async def sc_aging_deg(arguments: dict) -> str:
    """
    Perform age-stratified DEG analysis: Young vs Old, split by sex.
    Uses Wilcoxon rank-sum test. Identifies sex-specific aging genes.
    """
    adata_path = arguments.get("adata_path")
    young_groups = arguments.get("young_groups", ["03_months"])
    old_groups = arguments.get("old_groups", ["23_months"])
    genotype = arguments.get("genotype", "WT")
    cell_type = arguments.get("cell_type", None)
    n_top = arguments.get("n_top", 20)
    save_path = arguments.get("save_path", "/tmp/aging_deg_results.png")

    if not adata_path:
        return "❌ adata_path is required"

    try:
        import scanpy as sc
        import numpy as np
        import pandas as pd
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        adata = _load_and_filter(adata_path, genotype)
        if cell_type and "Main_cell_type" in adata.obs.columns:
            adata = adata[adata.obs["Main_cell_type"] == cell_type].copy()

        # Add age category
        adata.obs["age_category"] = "Middle"
        adata.obs.loc[adata.obs["Age_group"].isin(young_groups), "age_category"] = "Young"
        adata.obs.loc[adata.obs["Age_group"].isin(old_groups), "age_category"] = "Old"

        all_results = {}
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))

        for i, sex in enumerate(["Male", "Female"]):
            sub = adata[(adata.obs["Sex"] == sex) &
                        (adata.obs["age_category"].isin(["Young", "Old"]))].copy()

            n_young = (sub.obs["age_category"] == "Young").sum()
            n_old = (sub.obs["age_category"] == "Old").sum()

            if n_young < 3 or n_old < 3:
                all_results[sex] = {"error": f"Too few cells (Young={n_young}, Old={n_old})"}
                continue

            # Normalize if not already
            if sub.X.max() > 50:
                sc.pp.normalize_total(sub, target_sum=1e4)
                sc.pp.log1p(sub)

            sc.tl.rank_genes_groups(sub, groupby="age_category", groups=["Old"],
                                    reference="Young", method="wilcoxon")

            result = sc.get.rank_genes_groups_df(sub, group="Old")
            result = result.sort_values("pvals_adj")

            # Store top results
            top_up = result[result["logfoldchanges"] > 0].head(n_top)
            top_down = result[result["logfoldchanges"] < 0].head(n_top)

            n_deg_up = int(((result["pvals_adj"] < 0.05) & (result["logfoldchanges"] > 0.25)).sum()) if len(result) > 0 else 0
            n_deg_down = int(((result["pvals_adj"] < 0.05) & (result["logfoldchanges"] < -0.25)).sum()) if len(result) > 0 else 0

            all_results[sex] = {
                "n_young": int(n_young), "n_old": int(n_old),
                "n_deg_up": n_deg_up,
                "n_deg_down": n_deg_down,
                "top_up": top_up[["names", "logfoldchanges", "pvals_adj"]].head(10).to_dict("records"),
                "top_down": top_down[["names", "logfoldchanges", "pvals_adj"]].head(10).to_dict("records"),
            }

            # Volcano plot
            ax = axes[i]
            sig = result["pvals_adj"] < 0.05
            up = sig & (result["logfoldchanges"] > 0.25)
            down = sig & (result["logfoldchanges"] < -0.25)
            ns = ~(up | down)

            ax.scatter(result.loc[ns, "logfoldchanges"], -np.log10(result.loc[ns, "pvals_adj"].clip(1e-300)),
                      alpha=0.3, s=5, color="grey")
            ax.scatter(result.loc[up, "logfoldchanges"], -np.log10(result.loc[up, "pvals_adj"].clip(1e-300)),
                      alpha=0.5, s=10, color="#D6604D", label=f"Up ({up.sum()})")
            ax.scatter(result.loc[down, "logfoldchanges"], -np.log10(result.loc[down, "pvals_adj"].clip(1e-300)),
                      alpha=0.5, s=10, color="#4393C3", label=f"Down ({down.sum()})")

            # Label top genes
            for _, row in result.head(5).iterrows():
                ax.annotate(row["names"], (row["logfoldchanges"], -np.log10(max(row["pvals_adj"], 1e-300))),
                           fontsize=7, alpha=0.8)

            ax.set_title(f"{sex}: Old vs Young", fontweight="bold")
            ax.set_xlabel("Log2 Fold Change")
            ax.set_ylabel("-log10(adj p-value)")
            ax.axhline(-np.log10(0.05), ls="--", color="grey", alpha=0.5)
            ax.axvline(0.25, ls="--", color="grey", alpha=0.3)
            ax.axvline(-0.25, ls="--", color="grey", alpha=0.3)
            ax.legend(fontsize=8)

        plt.suptitle(f"Aging DEG: {young_groups} vs {old_groups}", fontsize=14, fontweight="bold")
        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        plt.close()

        # Build summary
        summary_lines = []
        for sex in ["Male", "Female"]:
            r = all_results.get(sex, {})
            if "error" in r:
                summary_lines.append(f"\n   {sex}: {r['error']}")
                continue
            summary_lines.append(f"\n   {sex} (Young={r['n_young']}, Old={r['n_old']}):")
            summary_lines.append(f"      ↑ Up in Old: {r['n_deg_up']} genes")
            summary_lines.append(f"      ↓ Down in Old: {r['n_deg_down']} genes")
            if r["top_up"]:
                top_names = [g["names"] for g in r["top_up"][:5]]
                summary_lines.append(f"      Top up: {', '.join(top_names)}")
            if r["top_down"]:
                top_names = [g["names"] for g in r["top_down"][:5]]
                summary_lines.append(f"      Top down: {', '.join(top_names)}")

        summary_str = "\n".join(summary_lines)

        return f"""🧬 Aging DEG Analysis Complete!

📊 Comparison: {young_groups} (Young) vs {old_groups} (Old)
🔬 Results:{summary_str}

💾 Volcano plot: {save_path}
🎯 Next: sc_sex_dimorphism to identify sex-specific aging patterns"""

    except Exception as e:
        logger.error(f"Aging DEG error: {e}", exc_info=True)
        return f"❌ {e}"


# ═══════════════════════════════════════════════════════════════════════════════
# Tool 5: Sex Dimorphism Analysis
# ═══════════════════════════════════════════════════════════════════════════════
async def sc_sex_dimorphism(arguments: dict) -> str:
    """
    Identify sex-dimorphic genes at each age point.
    Compares Male vs Female expression per age group to find
    genes with sex-specific aging patterns.
    """
    adata_path = arguments.get("adata_path")
    genes = arguments.get("genes", [])
    genotype = arguments.get("genotype", "WT")
    cell_type = arguments.get("cell_type", None)
    save_path = arguments.get("save_path", "/tmp/aging_sex_dimorphism.png")

    if not adata_path:
        return "❌ adata_path is required"

    try:
        import scanpy as sc
        import numpy as np
        import pandas as pd
        from scipy import stats
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        adata = _load_and_filter(adata_path, genotype)
        if cell_type and "Main_cell_type" in adata.obs.columns:
            adata = adata[adata.obs["Main_cell_type"] == cell_type].copy()

        # If no specific genes, find sex-dimorphic genes globally
        if not genes:
            # Run Male vs Female DEG across all ages
            sub = adata.copy()
            if sub.X.max() > 50:
                sc.pp.normalize_total(sub, target_sum=1e4)
                sc.pp.log1p(sub)
            sc.tl.rank_genes_groups(sub, groupby="Sex", groups=["Male"], reference="Female", method="wilcoxon")
            result_df = sc.get.rank_genes_groups_df(sub, group="Male")
            sig = result_df[result_df["pvals_adj"] < 0.05].sort_values("pvals_adj")
            genes = sig["names"].head(20).tolist()

            if not genes:
                return "❌ No significant sex-dimorphic genes found"

        valid_genes = [g for g in genes if g in adata.var_names]
        if not valid_genes:
            return f"❌ None of the genes found in data"

        # Per-age sex comparison
        records = []
        for gene in valid_genes:
            expr = _get_gene_expr(adata, gene)
            for age in AGE_ORDER:
                male_mask = (adata.obs["Sex"].values == "Male") & (adata.obs["Age_group"].values == age)
                female_mask = (adata.obs["Sex"].values == "Female") & (adata.obs["Age_group"].values == age)
                m_vals = expr[male_mask]
                f_vals = expr[female_mask]

                if len(m_vals) >= 3 and len(f_vals) >= 3:
                    stat, pval = stats.mannwhitneyu(m_vals, f_vals, alternative="two-sided")
                    log2fc = np.log2((np.mean(m_vals) + 0.01) / (np.mean(f_vals) + 0.01))
                    records.append({
                        "gene": gene, "age": age, "age_num": AGE_NUMERIC[age],
                        "male_mean": float(np.mean(m_vals)),
                        "female_mean": float(np.mean(f_vals)),
                        "log2fc_M_vs_F": float(log2fc),
                        "pval": float(pval),
                        "n_male": int(male_mask.sum()),
                        "n_female": int(female_mask.sum())
                    })

        if not records:
            return "❌ Insufficient cells for sex comparison"

        df = pd.DataFrame(records)

        # ── Heatmap: log2FC (Male/Female) across ages ──
        pivot = df.pivot_table(index="gene", columns="age", values="log2fc_M_vs_F")
        pivot = pivot.reindex(columns=AGE_ORDER)

        fig, ax = plt.subplots(figsize=(8, max(3, len(valid_genes) * 0.4)))
        import seaborn as sns
        sns.heatmap(pivot, cmap="RdBu_r", center=0, annot=True, fmt=".2f",
                    ax=ax, cbar_kws={"label": "log2FC (Male/Female)"})
        ax.set_title("Sex Dimorphism Across Aging", fontweight="bold")
        ax.set_ylabel("")
        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        plt.close()

        # Summary: genes that change dimorphism direction with age
        summary_lines = []
        for gene in valid_genes:
            gdf = df[df["gene"] == gene].sort_values("age_num")
            if len(gdf) >= 3:
                young_fc = gdf.iloc[0]["log2fc_M_vs_F"]
                old_fc = gdf.iloc[-1]["log2fc_M_vs_F"]
                if (young_fc > 0 and old_fc < 0) or (young_fc < 0 and old_fc > 0):
                    summary_lines.append(f"   🔄 {gene}: REVERSAL (young={young_fc:.2f} → old={old_fc:.2f})")
                elif abs(old_fc) > abs(young_fc) * 1.5:
                    summary_lines.append(f"   📈 {gene}: DIVERGING (young={young_fc:.2f} → old={old_fc:.2f})")
                elif abs(old_fc) < abs(young_fc) * 0.5:
                    summary_lines.append(f"   📉 {gene}: CONVERGING (young={young_fc:.2f} → old={old_fc:.2f})")
                else:
                    summary_lines.append(f"   → {gene}: stable (young={young_fc:.2f} → old={old_fc:.2f})")

        summary_str = "\n".join(summary_lines) if summary_lines else "   Insufficient data for pattern analysis"

        return f"""⚤ Sex Dimorphism Analysis Complete!

📊 Genes analyzed: {len(valid_genes)}
🧬 Cells: {adata.n_obs} ({genotype})

🔬 Sex × Aging Patterns:
{summary_str}

💡 Pattern Legend:
   🔄 REVERSAL: Male-biased → Female-biased (or vice versa)
   📈 DIVERGING: Sex difference increases with age
   📉 CONVERGING: Sex difference decreases with age

💾 Heatmap: {save_path}"""

    except Exception as e:
        logger.error(f"Sex dimorphism error: {e}", exc_info=True)
        return f"❌ {e}"
