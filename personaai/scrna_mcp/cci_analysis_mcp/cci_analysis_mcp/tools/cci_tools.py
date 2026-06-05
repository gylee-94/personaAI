"""
CCI Analysis Tools for Aging Hypothesis Validation (LIANA+ based)

Tools:
1. cci_run_analysis       - Run LIANA rank_aggregate on h5ad
2. cci_compare_aging      - Compare CCI between Young vs Old (sex-stratified)
3. cci_query_interactions - Query specific L-R pairs or cell type pairs
4. cci_plot_dotplot       - Dotplot visualization of interactions
5. cci_plot_network       - Network/chord visualization of interactions
"""
import logging
import os

logger = logging.getLogger("cci-analysis-mcp")

# ─── Constants ────────────────────────────────────────────────────────────────
CCI_DATA_DIR = os.environ.get("CCI_DATA_DIR", "./cci_data")
AGE_ORDER = ["03_months", "06_months", "12_months", "16_months", "23_months"]
AGE_NUMERIC = {"03_months": 3, "06_months": 6, "12_months": 12, "16_months": 16, "23_months": 23}


def _detect_organism(adata):
    """Detect human vs mouse from gene names."""
    gene_sample = list(adata.var_names[:100])
    upper_count = sum(1 for g in gene_sample if g == g.upper())
    return "human" if upper_count > 50 else "mouse"


def _get_resource(organism: str, resource_name: str = None):
    """Get L-R resource, preferring local cache."""
    if resource_name:
        local_path = os.path.join(CCI_DATA_DIR, f"{resource_name}_ligand_receptor.csv")
        if os.path.exists(local_path):
            import pandas as pd
            return pd.read_csv(local_path)

    if organism == "mouse":
        local_path = os.path.join(CCI_DATA_DIR, "mouseconsensus_ligand_receptor.csv")
        if os.path.exists(local_path):
            import pandas as pd
            return pd.read_csv(local_path)
        return "mouseconsensus"
    else:
        local_path = os.path.join(CCI_DATA_DIR, "consensus_ligand_receptor.csv")
        if os.path.exists(local_path):
            import pandas as pd
            return pd.read_csv(local_path)
        return "consensus"


def _as_clean_category(adata, column: str) -> None:
    """Ensure an obs column is categorical and remove unused categories."""
    adata.obs[column] = adata.obs[column].astype("category")
    adata.obs[column] = adata.obs[column].cat.remove_unused_categories()


def _missing_obs_columns(adata, columns):
    return [col for col in columns if col not in adata.obs.columns]


# ═══════════════════════════════════════════════════════════════════════════════
# Tool 1: Run LIANA Analysis
# ═══════════════════════════════════════════════════════════════════════════════
async def cci_run_analysis(arguments: dict) -> str:
    """
    Run LIANA rank_aggregate on an h5ad file.
    Accepts h5ad from sc_analysis_mcp pipeline (shared via file path).
    """
    adata_path = arguments.get("adata_path")
    groupby = arguments.get("groupby", "Main_cell_type")
    resource_name = arguments.get("resource_name", None)
    min_cells = arguments.get("min_cells", 10)
    expr_prop = arguments.get("expr_prop", 0.1)
    output_path = arguments.get("output_path", "/tmp/cci_results.h5ad")

    if not adata_path:
        return "❌ adata_path is required"

    try:
        import scanpy as sc
        import liana as li
        import pandas as pd

        adata = sc.read_h5ad(adata_path)
        logger.info(f"Loaded {adata.n_obs} cells, {adata.n_vars} genes")

        # Validate groupby column
        if groupby not in adata.obs.columns:
            available = [c for c in adata.obs.columns if "cell" in c.lower() or "type" in c.lower() or "cluster" in c.lower()]
            return f"❌ '{groupby}' not found. Cell type columns: {available}\nAll columns: {list(adata.obs.columns)}"

        # Filter small cell types
        type_counts = adata.obs[groupby].value_counts()
        valid_types = type_counts[type_counts >= min_cells].index.tolist()
        if len(valid_types) < 2:
            return f"❌ Need ≥2 cell types with ≥{min_cells} cells. Found: {dict(type_counts)}"

        adata = adata[adata.obs[groupby].isin(valid_types)].copy()
        _as_clean_category(adata, groupby)

        # Normalize if needed
        if adata.X.max() > 50:
            sc.pp.normalize_total(adata, target_sum=1e4)
            sc.pp.log1p(adata)

        # Detect organism and get resource
        organism = _detect_organism(adata)
        resource = _get_resource(organism, resource_name)
        resource_label = resource_name or ("mouseconsensus" if organism == "mouse" else "consensus")

        logger.info(f"Running LIANA: organism={organism}, resource={resource_label}")

        # Run LIANA
        if isinstance(resource, str):
            li.mt.rank_aggregate(
                adata,
                groupby=groupby,
                resource_name=resource,
                expr_prop=expr_prop,
                verbose=True,
                use_raw=False
            )
        else:
            li.mt.rank_aggregate(
                adata,
                groupby=groupby,
                resource=resource,
                expr_prop=expr_prop,
                verbose=True,
                use_raw=False
            )

        # Extract results
        liana_res = adata.uns["liana_res"]
        n_interactions = len(liana_res)

        # Top interactions
        top = liana_res.sort_values("magnitude_rank").head(15)
        top_str = "\n".join([
            f"   {row['source']} → {row['target']}: {row['ligand_complex']}→{row['receptor_complex']} "
            f"(mag={row['magnitude_rank']:.4f}, spec={row['specificity_rank']:.4f})"
            for _, row in top.iterrows()
        ])

        # Cell type summary
        ct_str = "\n".join([f"   {ct}: {cnt} cells" for ct, cnt in type_counts[valid_types].items()])

        # Save
        adata.write_h5ad(output_path)

        return f"""🔗 LIANA CCI Analysis Complete!

📊 Dataset: {adata.n_obs} cells, {len(valid_types)} cell types
🧬 Organism: {organism} | Resource: {resource_label}
📈 Total interactions found: {n_interactions}

🏘️ Cell types analyzed:
{ct_str}

🔝 Top 15 interactions (by magnitude):
{top_str}

💾 Results saved: {output_path}
   (liana_res stored in adata.uns['liana_res'])

🎯 Next: cci_query_interactions or cci_compare_aging"""

    except Exception as e:
        logger.error(f"CCI analysis error: {e}", exc_info=True)
        return f"❌ {e}"


# ═══════════════════════════════════════════════════════════════════════════════
# Tool 2: Compare CCI Aging (Young vs Old, sex-stratified)
# ═══════════════════════════════════════════════════════════════════════════════
async def cci_compare_aging(arguments: dict) -> str:
    """
    Compare cell-cell interactions between Young vs Old, stratified by sex.
    Runs LIANA separately for each age×sex group, then computes differential
    interaction scores.
    """
    adata_path = arguments.get("adata_path")
    groupby = arguments.get("groupby", "Main_cell_type")
    young_groups = arguments.get("young_groups", ["03_months"])
    old_groups = arguments.get("old_groups", ["23_months"])
    resource_name = arguments.get("resource_name", None)
    min_cells = arguments.get("min_cells", 10)
    expr_prop = arguments.get("expr_prop", 0.1)
    genotype = arguments.get("genotype", "WT")
    save_path = arguments.get("save_path", "/tmp/cci_aging_comparison.png")

    if not adata_path:
        return "❌ adata_path is required"

    try:
        import scanpy as sc
        import liana as li
        import pandas as pd
        import numpy as np
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        adata = sc.read_h5ad(adata_path)

        # Filter genotype
        if genotype and "Genotype" in adata.obs.columns:
            adata = adata[adata.obs["Genotype"] == genotype].copy()

        if groupby not in adata.obs.columns:
            return f"❌ '{groupby}' not found in obs columns"

        missing = _missing_obs_columns(adata, ["Sex", "Age_group"])
        if missing:
            return f"""❌ Missing required obs column(s): {missing}

Required for aging comparison: Sex, Age_group, and {groupby}
Available columns: {list(adata.obs.columns)}"""

        # Normalize if needed
        if adata.X.max() > 50:
            sc.pp.normalize_total(adata, target_sum=1e4)
            sc.pp.log1p(adata)

        organism = _detect_organism(adata)
        resource = _get_resource(organism, resource_name)
        resource_label = resource_name or ("mouseconsensus" if organism == "mouse" else "consensus")

        # Run LIANA per condition
        conditions = {}
        for sex in ["Male", "Female"]:
            for age_label, age_groups in [("Young", young_groups), ("Old", old_groups)]:
                key = f"{sex}_{age_label}"
                sub = adata[
                    (adata.obs["Sex"] == sex) &
                    (adata.obs["Age_group"].isin(age_groups))
                ].copy()

                # Filter cell types with enough cells
                ct_counts = sub.obs[groupby].value_counts()
                valid_cts = ct_counts[ct_counts >= min_cells].index.tolist()

                if len(valid_cts) < 2:
                    conditions[key] = {"error": f"Too few cell types (n={len(valid_cts)}, need ≥2)", "n_cells": sub.n_obs}
                    continue

                sub = sub[sub.obs[groupby].isin(valid_cts)].copy()
                _as_clean_category(sub, groupby)

                try:
                    if isinstance(resource, str):
                        li.mt.rank_aggregate(sub, groupby=groupby, resource_name=resource,
                                            expr_prop=expr_prop, verbose=False, use_raw=False)
                    else:
                        li.mt.rank_aggregate(sub, groupby=groupby, resource=resource,
                                            expr_prop=expr_prop, verbose=False, use_raw=False)

                    res = sub.uns["liana_res"].copy()
                    res["condition"] = key
                    conditions[key] = {"results": res, "n_cells": sub.n_obs, "n_types": len(valid_cts)}
                except Exception as ex:
                    conditions[key] = {"error": str(ex), "n_cells": sub.n_obs}

        # Compute differential interactions per sex
        diff_results = {}
        for sex in ["Male", "Female"]:
            young_key = f"{sex}_Young"
            old_key = f"{sex}_Old"

            if "error" in conditions.get(young_key, {"error": "missing"}):
                diff_results[sex] = {"error": conditions.get(young_key, {}).get("error", "No Young data")}
                continue
            if "error" in conditions.get(old_key, {"error": "missing"}):
                diff_results[sex] = {"error": conditions.get(old_key, {}).get("error", "No Old data")}
                continue

            young_res = conditions[young_key]["results"]
            old_res = conditions[old_key]["results"]

            # Merge on interaction identity
            merge_cols = ["source", "target", "ligand_complex", "receptor_complex"]
            merged = pd.merge(
                young_res[merge_cols + ["magnitude_rank", "specificity_rank"]],
                old_res[merge_cols + ["magnitude_rank", "specificity_rank"]],
                on=merge_cols, suffixes=("_young", "_old"), how="outer"
            )

            # Delta rank (negative = stronger in old)
            merged["delta_magnitude"] = merged["magnitude_rank_old"].fillna(1) - merged["magnitude_rank_young"].fillna(1)
            merged["delta_specificity"] = merged["specificity_rank_old"].fillna(1) - merged["specificity_rank_young"].fillna(1)

            # Gained in old (present in old, absent/weak in young)
            gained = merged[
                (merged["magnitude_rank_old"] < 0.05) &
                ((merged["magnitude_rank_young"].isna()) | (merged["magnitude_rank_young"] > 0.3))
            ].sort_values("magnitude_rank_old").head(10)

            # Lost in old (present in young, absent/weak in old)
            lost = merged[
                (merged["magnitude_rank_young"] < 0.05) &
                ((merged["magnitude_rank_old"].isna()) | (merged["magnitude_rank_old"] > 0.3))
            ].sort_values("magnitude_rank_young").head(10)

            diff_results[sex] = {
                "merged": merged,
                "n_total": len(merged),
                "gained": gained,
                "lost": lost,
                "n_young": conditions[young_key]["n_cells"],
                "n_old": conditions[old_key]["n_cells"]
            }

        # ── Plot: scatter of Young vs Old magnitude_rank per sex ──
        fig, axes = plt.subplots(1, 2, figsize=(12, 5))
        for i, sex in enumerate(["Male", "Female"]):
            ax = axes[i]
            r = diff_results.get(sex, {})
            if "error" in r:
                ax.text(0.5, 0.5, r["error"], ha="center", va="center", transform=ax.transAxes)
                ax.set_title(f"{sex}: Error")
                continue

            m = r["merged"].dropna(subset=["magnitude_rank_young", "magnitude_rank_old"])
            ax.scatter(m["magnitude_rank_young"], m["magnitude_rank_old"], alpha=0.3, s=10, color="grey")

            # Highlight gained/lost
            if len(r["gained"]) > 0:
                g = r["gained"].dropna(subset=["magnitude_rank_young", "magnitude_rank_old"])
                ax.scatter(g["magnitude_rank_young"], g["magnitude_rank_old"], color="#D6604D", s=30, label=f"Gained ({len(r['gained'])})", zorder=5)
            if len(r["lost"]) > 0:
                l = r["lost"].dropna(subset=["magnitude_rank_young", "magnitude_rank_old"])
                ax.scatter(l["magnitude_rank_young"], l["magnitude_rank_old"], color="#4393C3", s=30, label=f"Lost ({len(r['lost'])})", zorder=5)

            ax.plot([0, 1], [0, 1], "k--", alpha=0.3)
            ax.set_xlabel("Young (magnitude_rank)")
            ax.set_ylabel("Old (magnitude_rank)")
            ax.set_title(f"{sex} (Young={r['n_young']}, Old={r['n_old']})", fontweight="bold")
            ax.legend(fontsize=8)
            ax.set_xlim(-0.02, 1.02)
            ax.set_ylim(-0.02, 1.02)

        plt.suptitle(f"CCI Aging Comparison: {young_groups} vs {old_groups}", fontsize=13, fontweight="bold")
        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        plt.close()

        # ── Summary ──
        summary_lines = []
        for sex in ["Male", "Female"]:
            r = diff_results.get(sex, {})
            if "error" in r:
                summary_lines.append(f"\n   {sex}: ❌ {r['error']}")
                continue

            summary_lines.append(f"\n   {sex} (Young={r['n_young']}, Old={r['n_old']}):")
            summary_lines.append(f"      Total interactions compared: {r['n_total']}")

            if len(r["gained"]) > 0:
                gained_str = "; ".join([
                    f"{row['source']}→{row['target']}:{row['ligand_complex']}→{row['receptor_complex']}"
                    for _, row in r["gained"].head(5).iterrows()
                ])
                summary_lines.append(f"      🔴 Gained in Old: {gained_str}")

            if len(r["lost"]) > 0:
                lost_str = "; ".join([
                    f"{row['source']}→{row['target']}:{row['ligand_complex']}→{row['receptor_complex']}"
                    for _, row in r["lost"].head(5).iterrows()
                ])
                summary_lines.append(f"      🔵 Lost in Old: {lost_str}")

        summary_str = "\n".join(summary_lines)

        return f"""⏳ CCI Aging Comparison Complete!

📊 Young: {young_groups} vs Old: {old_groups} | Genotype: {genotype}
🔬 Results:{summary_str}

💾 Plot: {save_path}
🎯 Next: cci_query_interactions to check specific L-R pairs"""

    except Exception as e:
        logger.error(f"CCI aging comparison error: {e}", exc_info=True)
        return f"❌ {e}"


# ═══════════════════════════════════════════════════════════════════════════════
# Tool 3: Query Specific Interactions
# ═══════════════════════════════════════════════════════════════════════════════
async def cci_query_interactions(arguments: dict) -> str:
    """
    Query specific L-R pairs or cell type pairs from LIANA results.
    Use after cci_run_analysis. Supports filtering by ligand, receptor,
    source/target cell type.
    """
    adata_path = arguments.get("adata_path")
    ligands = arguments.get("ligands", [])
    receptors = arguments.get("receptors", [])
    source_cells = arguments.get("source_cells", [])
    target_cells = arguments.get("target_cells", [])
    max_magnitude_rank = arguments.get("max_magnitude_rank", 0.05)
    export_path = arguments.get("export_path", None)

    if not adata_path:
        return "❌ adata_path is required (must contain liana_res in .uns)"

    try:
        import scanpy as sc
        import pandas as pd

        adata = sc.read_h5ad(adata_path)

        if "liana_res" not in adata.uns:
            return "❌ No LIANA results found. Run cci_run_analysis first."

        res = adata.uns["liana_res"].copy()
        original_n = len(res)

        # Apply filters
        if ligands:
            res = res[res["ligand_complex"].isin(ligands)]
        if receptors:
            res = res[res["receptor_complex"].isin(receptors)]
        if source_cells:
            res = res[res["source"].isin(source_cells)]
        if target_cells:
            res = res[res["target"].isin(target_cells)]
        if max_magnitude_rank:
            res = res[res["magnitude_rank"] <= max_magnitude_rank]

        res = res.sort_values("magnitude_rank")

        if len(res) == 0:
            return f"""❌ No interactions found with current filters.
Filters applied: ligands={ligands}, receptors={receptors}, source={source_cells}, target={target_cells}, max_rank={max_magnitude_rank}
Total interactions in dataset: {original_n}"""

        # Format results
        top_n = min(30, len(res))
        result_str = "\n".join([
            f"   {row['source']:>20s} → {row['target']:<20s} | "
            f"{row['ligand_complex']:>12s} → {row['receptor_complex']:<12s} | "
            f"mag={row['magnitude_rank']:.4f} spec={row['specificity_rank']:.4f}"
            for _, row in res.head(top_n).iterrows()
        ])

        # Summary by cell type pair
        pair_counts = res.groupby(["source", "target"]).size().sort_values(ascending=False)
        pair_str = "\n".join([
            f"   {src} → {tgt}: {cnt} interactions"
            for (src, tgt), cnt in pair_counts.head(10).items()
        ])

        # Export if requested
        export_msg = ""
        if export_path:
            res.to_csv(export_path, index=False)
            export_msg = f"\n💾 Exported {len(res)} interactions to: {export_path}"

        return f"""🔍 CCI Query Results

📊 {len(res)} interactions found (from {original_n} total)
🔎 Filters: ligands={ligands or 'all'}, receptors={receptors or 'all'}, source={source_cells or 'all'}, target={target_cells or 'all'}

📋 Top {top_n} interactions:
{result_str}

🏘️ By cell type pair:
{pair_str}{export_msg}"""

    except Exception as e:
        logger.error(f"CCI query error: {e}", exc_info=True)
        return f"❌ {e}"


# ═══════════════════════════════════════════════════════════════════════════════
# Tool 4: Dotplot Visualization
# ═══════════════════════════════════════════════════════════════════════════════
async def cci_plot_dotplot(arguments: dict) -> str:
    """
    Create LIANA dotplot visualization of cell-cell interactions.
    """
    adata_path = arguments.get("adata_path")
    source_cells = arguments.get("source_cells", None)
    target_cells = arguments.get("target_cells", None)
    top_n = arguments.get("top_n", 20)
    magnitude_metric = arguments.get("magnitude_metric", "magnitude_rank")
    specificity_metric = arguments.get("specificity_metric", "specificity_rank")
    save_path = arguments.get("save_path", "/tmp/cci_dotplot.png")

    if not adata_path:
        return "❌ adata_path is required"

    try:
        import scanpy as sc
        import liana as li
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        adata = sc.read_h5ad(adata_path)

        if "liana_res" not in adata.uns:
            return "❌ No LIANA results found. Run cci_run_analysis first."

        # Filter before plotting
        liana_res = adata.uns["liana_res"].copy()

        if source_cells:
            liana_res = liana_res[liana_res["source"].isin(source_cells)]
        if target_cells:
            liana_res = liana_res[liana_res["target"].isin(target_cells)]

        # Get top interactions
        liana_res = liana_res.sort_values("magnitude_rank").head(top_n)
        adata.uns["liana_res"] = liana_res

        fig, ax = plt.subplots(figsize=(10, max(4, top_n * 0.35)))

        try:
            li.pl.dotplot(
                adata=adata,
                colour=magnitude_metric,
                size=specificity_metric,
                inverse_size=True,
                inverse_colour=True,
                source_labels=source_cells,
                target_labels=target_cells,
                top_n=top_n,
                figure_size=(10, max(4, top_n * 0.35))
            )
            plt.savefig(save_path, dpi=150, bbox_inches="tight")
            plt.close("all")

        except Exception:
            # Fallback: manual dotplot
            import seaborn as sns
            import numpy as np

            liana_res["interaction"] = (
                liana_res["ligand_complex"] + "→" + liana_res["receptor_complex"]
            )
            liana_res["cell_pair"] = liana_res["source"] + " → " + liana_res["target"]

            pivot_color = liana_res.pivot_table(
                index="interaction", columns="cell_pair",
                values="magnitude_rank", aggfunc="first"
            )

            fig, ax = plt.subplots(figsize=(max(6, len(pivot_color.columns) * 1.2), max(4, len(pivot_color) * 0.4)))
            sns.heatmap(
                pivot_color, cmap="RdYlBu", annot=True, fmt=".3f",
                ax=ax, cbar_kws={"label": "magnitude_rank (lower=stronger)"}
            )
            ax.set_title("CCI Interactions (magnitude_rank)", fontweight="bold")
            plt.tight_layout()
            plt.savefig(save_path, dpi=150, bbox_inches="tight")
            plt.close()

        return f"""📊 CCI Dotplot Complete!

📈 Top {top_n} interactions plotted
💾 {save_path}
🎯 Next: cci_compare_aging or cci_query_interactions"""

    except Exception as e:
        logger.error(f"CCI dotplot error: {e}", exc_info=True)
        return f"❌ {e}"


# ═══════════════════════════════════════════════════════════════════════════════
# Tool 5: Network Visualization
# ═══════════════════════════════════════════════════════════════════════════════
async def cci_plot_network(arguments: dict) -> str:
    """
    Create network/chord diagram of cell-cell interactions.
    Shows interaction strength between cell types.
    """
    adata_path = arguments.get("adata_path")
    top_n = arguments.get("top_n", 30)
    magnitude_threshold = arguments.get("magnitude_threshold", 0.05)
    save_path = arguments.get("save_path", "/tmp/cci_network.png")

    if not adata_path:
        return "❌ adata_path is required"

    try:
        import scanpy as sc
        import pandas as pd
        import numpy as np
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches

        adata = sc.read_h5ad(adata_path)

        if "liana_res" not in adata.uns:
            return "❌ No LIANA results found. Run cci_run_analysis first."

        res = adata.uns["liana_res"]
        sig = res[res["magnitude_rank"] <= magnitude_threshold]

        # Count interactions per cell type pair
        pair_counts = sig.groupby(["source", "target"]).size().reset_index(name="n_interactions")
        pair_counts = pair_counts.sort_values("n_interactions", ascending=False).head(top_n)

        all_types = sorted(set(pair_counts["source"].tolist() + pair_counts["target"].tolist()))
        n_types = len(all_types)

        if n_types == 0:
            return f"❌ No significant interactions at threshold {magnitude_threshold}"

        # Circular layout
        fig, ax = plt.subplots(figsize=(10, 10))

        angles = np.linspace(0, 2 * np.pi, n_types, endpoint=False)
        positions = {ct: (np.cos(a), np.sin(a)) for ct, a in zip(all_types, angles)}

        # Color map
        cmap = plt.cm.Set3(np.linspace(0, 1, n_types))
        colors = {ct: cmap[i] for i, ct in enumerate(all_types)}

        # Draw edges
        max_count = pair_counts["n_interactions"].max()
        for _, row in pair_counts.iterrows():
            src_pos = positions[row["source"]]
            tgt_pos = positions[row["target"]]
            width = (row["n_interactions"] / max_count) * 4 + 0.5
            alpha = min(0.8, (row["n_interactions"] / max_count) * 0.6 + 0.2)

            ax.annotate(
                "", xy=tgt_pos, xytext=src_pos,
                arrowprops=dict(
                    arrowstyle="-|>", color=colors[row["source"]],
                    lw=width, alpha=alpha,
                    connectionstyle="arc3,rad=0.15"
                )
            )

        # Draw nodes
        for ct in all_types:
            x, y = positions[ct]
            ax.scatter(x, y, s=600, c=[colors[ct]], zorder=5, edgecolors="black", linewidth=1.5)
            offset = 0.15
            ax.text(x * (1 + offset), y * (1 + offset), ct,
                    ha="center", va="center", fontsize=9, fontweight="bold")

        ax.set_xlim(-1.6, 1.6)
        ax.set_ylim(-1.6, 1.6)
        ax.set_aspect("equal")
        ax.axis("off")
        ax.set_title(f"CCI Network (magnitude_rank ≤ {magnitude_threshold})", fontsize=14, fontweight="bold")

        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        plt.close()

        # Summary
        summary = pair_counts.head(10)
        summary_str = "\n".join([
            f"   {row['source']} → {row['target']}: {row['n_interactions']} interactions"
            for _, row in summary.iterrows()
        ])

        return f"""🕸️ CCI Network Plot Complete!

📊 {len(sig)} significant interactions (rank ≤ {magnitude_threshold})
🏘️ {n_types} cell types in network

🔝 Top cell type pairs:
{summary_str}

💾 {save_path}"""

    except Exception as e:
        logger.error(f"CCI network error: {e}", exc_info=True)
        return f"❌ {e}"
