#!/usr/bin/env python3
# =============================================================================
# CONFIDENTIAL & PROPRIETARY
# =============================================================================
# Copyright (c) 2025 KJ Lab, Cedars-Sinai Medical Center. All Rights Reserved.
#
# This source code is STRICTLY CONFIDENTIAL and PROPRIETARY.
# Unauthorized copying, distribution, modification, or use of this code,
# in whole or in part, is strictly prohibited without prior written
# permission from the author.
#
# WARNING:
#   - DO NOT share, redistribute, or publish this code.
#   - DO NOT upload to public repositories (GitHub, GitLab, etc.).
#   - DO NOT use for commercial purposes without authorization.
#   - Violation may result in legal action.
#
# 본 소스코드는 기밀이며 저작권법에 의해 보호됩니다.
# 무단 복제, 배포, 수정, 공유를 엄격히 금지합니다.
# =============================================================================

"""
Differential Expression Gene (DEG) Analysis Tools
Functions for finding marker genes and DEGs using scanpy
"""

import logging
import pandas as pd
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns
from ..h5ad_compat import read_h5ad_compat

logger = logging.getLogger(__name__)


class _LazyScanpy:
    def __getattr__(self, name):
        import scanpy
        return getattr(scanpy, name)


sc = _LazyScanpy()

# =============================================================================
# Supported Color Palettes Reference for DEG Visualization
# =============================================================================
DEG_PALETTE_HELP = """
💡 Available color options for DEG plots:

📊 Heatmap/Dotplot colormaps:
   viridis, plasma, inferno, magma, cividis
   Reds, Blues, Greens, YlOrRd, RdBu_r, coolwarm

🌋 Volcano/MA plot colors:
   up_color: '#e74c3c' (red), '#FF6B6B', 'crimson'
   down_color: '#3498db' (blue), '#4ECDC4', 'steelblue'
   ns_color: '#95a5a6' (gray), '#BDC3C7', 'lightgray'

🎨 Custom example:
   colors={'up': '#FF0000', 'down': '#0000FF', 'ns': '#808080'}
"""

async def sc_find_markers(args: dict) -> str:
    """
    Find marker genes for each cluster using scanpy.tl.rank_genes_groups
    
    Args:
        adata_path: Path to h5ad file (after clustering)
        groupby: Column name to group by (default: 'leiden')
        method: Statistical test method ('t-test', 'wilcoxon', 'logreg')
        n_genes: Number of top genes per group
        use_raw: Whether to use raw counts
        corr_method: Multiple testing correction method ('bonferroni', 'fdr_bh')
        key_added: Key to store results in adata.uns (default: 'rank_genes_groups')
    
    Returns:
        Success message with summary statistics
    """
    try:
        adata_path = args.get("adata_path", "/tmp/sc_umap.h5ad")
        groupby = args.get("groupby", "leiden")
        method = args.get("method", "wilcoxon")
        n_genes = args.get("n_genes", 100)
        use_raw = args.get("use_raw", True)
        corr_method = args.get("corr_method", "fdr_bh")
        # Map fdr_bh to benjamini-hochberg for scanpy compatibility
        if corr_method == "fdr_bh":
            corr_method = "benjamini-hochberg"
        key_added = args.get("key_added", "rank_genes_groups")

        logger.info(f"🔍 Finding marker genes from {adata_path}")
        
        # Load data
        adata = read_h5ad_compat(adata_path)
        
        # Validate groupby column
        if groupby not in adata.obs.columns:
            raise ValueError(f"Column '{groupby}' not found in adata.obs")
        
        # Check if raw data exists
        if use_raw and adata.raw is None:
            logger.warning("⚠️ No raw data found, using normalized data")
            use_raw = False
        
        # Run differential expression analysis
        logger.info(f"📊 Computing DEGs using {method} test...")
        sc.tl.rank_genes_groups(
            adata,
            groupby=groupby,
            method=method,
            n_genes=n_genes,
            use_raw=use_raw,
            corr_method=corr_method,
            key_added=key_added
        )
        
        # Save results
        output_path = adata_path.replace(".h5ad", "_deg.h5ad")
        adata.write_h5ad(output_path)
        logger.info(f"💾 Saved to {output_path}")
        
        # Generate summary
        n_groups = len(adata.obs[groupby].unique())
        result_summary = f"""
✅ Marker gene analysis completed!

📋 Analysis Parameters:
  • Grouping: {groupby} ({n_groups} groups)
  • Method: {method}
  • Top genes per group: {n_genes}
  • Use raw counts: {use_raw}
  • Correction method: {corr_method}
  
💾 Results saved to:
  • {output_path}
  • DEG results stored in adata.uns['{key_added}']

📊 Summary Statistics:
  • Total cells: {adata.n_obs:,}
  • Total genes tested: {adata.n_vars:,}
  • Groups analyzed: {n_groups}
  • Genes per group: {n_genes}
  
💡 Next steps:
  1. Use sc_get_deg_results to view top genes
  2. Use sc_export_deg to save results as CSV/Excel
  3. Use sc_plot_deg_heatmap/dotplot for visualization
"""
        return result_summary
        
    except Exception as e:
        logger.error(f"Error in sc_find_markers: {e}", exc_info=True)
        raise


async def sc_get_deg_results(args: dict) -> str:
    """
    Get DEG results table with filtering options
    
    Args:
        adata_path: Path to h5ad file with DEG results
        key: Key in adata.uns containing results (default: 'rank_genes_groups')
        group: Specific group to show (optional, shows all if not specified)
        n_genes: Number of top genes to show per group (default: 10)
        pval_cutoff: P-value cutoff for filtering (default: 0.05)
        logfc_cutoff: Log fold-change cutoff (default: 0.5)
    
    Returns:
        Formatted table of DEG results
    """
    try:
        adata_path = args.get("adata_path", "/tmp/sc_umap_deg.h5ad")
        key = args.get("key", "rank_genes_groups")
        group = args.get("group")
        n_genes = args.get("n_genes", 10)
        pval_cutoff = args.get("pval_cutoff", 0.05)
        logfc_cutoff = args.get("logfc_cutoff", 0.5)
        
        logger.info(f"📊 Loading DEG results from {adata_path}")
        
        # Load data
        adata = read_h5ad_compat(adata_path)
        
        # Check if results exist
        if key not in adata.uns:
            raise ValueError(f"No DEG results found at adata.uns['{key}']. Run sc_find_markers first.")
        
        # Get results as DataFrame
        result = sc.get.rank_genes_groups_df(adata, group=group, key=key)
        
        # Apply filters
        filtered = result[
            (result['pvals_adj'] < pval_cutoff) & 
            (result['logfoldchanges'].abs() > logfc_cutoff)
        ]
        
        # Get top genes per group
        if group is None:
            # Show top genes for each group
            top_genes = []
            for grp in result['group'].unique():
                grp_data = filtered[filtered['group'] == grp].head(n_genes)
                top_genes.append(grp_data)
            display_df = pd.concat(top_genes)
        else:
            display_df = filtered.head(n_genes)
        
        # Format output
        output = f"""
📊 Differentially Expressed Genes

🔍 Filtering Criteria:
  • Adjusted p-value < {pval_cutoff}
  • |Log fold-change| > {logfc_cutoff}
  • Top {n_genes} genes per group

📈 Results ({len(display_df)} genes):

{display_df.to_string(index=False)}

📋 Summary:
  • Total significant genes: {len(filtered):,}
  • Groups analyzed: {result['group'].nunique()}
  • Displaying: {len(display_df)} genes
"""
        return output
        
    except Exception as e:
        logger.error(f"Error in sc_get_deg_results: {e}", exc_info=True)
        raise


async def sc_export_deg(args: dict) -> str:
    """
    Export DEG results to CSV or Excel files
    
    Args:
        adata_path: Path to h5ad file with DEG results
        key: Key in adata.uns containing results (default: 'rank_genes_groups')
        output_dir: Directory to save results (default: /tmp/deg_results)
        format: Export format ('csv', 'excel', 'both')
        pval_cutoff: P-value cutoff for filtering (default: 0.05)
        logfc_cutoff: Log fold-change cutoff (default: 0.5)
    
    Returns:
        Paths to exported files
    """
    try:
        adata_path = args.get("adata_path", "/tmp/sc_umap_deg.h5ad")
        key = args.get("key", "rank_genes_groups")
        output_dir = args.get("output_dir", "/tmp/deg_results")
        export_format = args.get("format", "both")
        pval_cutoff = args.get("pval_cutoff", 0.05)
        logfc_cutoff = args.get("logfc_cutoff", 0.5)
        
        logger.info(f"📁 Exporting DEG results to {output_dir}")
        
        # Create output directory
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # Load data
        adata = read_h5ad_compat(adata_path)
        
        if key not in adata.uns:
            raise ValueError(f"No DEG results found at adata.uns['{key}']")
        
        # Get all results
        all_results = sc.get.rank_genes_groups_df(adata, group=None, key=key)
        
        # Apply filters
        filtered = all_results[
            (all_results['pvals_adj'] < pval_cutoff) & 
            (all_results['logfoldchanges'].abs() > logfc_cutoff)
        ]
        
        exported_files = []
        
        # Export to CSV
        if export_format in ['csv', 'both']:
            # All results
            all_csv = f"{output_dir}/deg_all_genes.csv"
            all_results.to_csv(all_csv, index=False)
            exported_files.append(all_csv)
            
            # Filtered results
            filtered_csv = f"{output_dir}/deg_significant.csv"
            filtered.to_csv(filtered_csv, index=False)
            exported_files.append(filtered_csv)
            
            # Per-group results
            for group in all_results['group'].unique():
                group_data = filtered[filtered['group'] == group]
                group_csv = f"{output_dir}/deg_group_{group}.csv"
                group_data.to_csv(group_csv, index=False)
                exported_files.append(group_csv)
        
        # Export to Excel
        if export_format in ['excel', 'both']:
            excel_path = f"{output_dir}/deg_results.xlsx"
            with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
                all_results.to_excel(writer, sheet_name='All_Genes', index=False)
                filtered.to_excel(writer, sheet_name='Significant', index=False)
                
                # Each group in separate sheet
                for group in all_results['group'].unique():
                    group_data = filtered[filtered['group'] == group]
                    sheet_name = f"Group_{group}"[:31]  # Excel sheet name limit
                    group_data.to_excel(writer, sheet_name=sheet_name, index=False)
            
            exported_files.append(excel_path)
        
        result = f"""
✅ DEG results exported successfully!

📁 Output Directory: {output_dir}

📊 Exported Files ({len(exported_files)}):
"""
        for f in exported_files:
            result += f"\n  • {f}"
        
        result += f"""

📈 Export Summary:
  • Total genes tested: {len(all_results):,}
  • Significant genes: {len(filtered):,}
  • P-value cutoff: {pval_cutoff}
  • Log FC cutoff: {logfc_cutoff}
  • Groups: {all_results['group'].nunique()}
"""
        return result
        
    except Exception as e:
        logger.error(f"Error in sc_export_deg: {e}", exc_info=True)
        raise


async def sc_plot_deg_heatmap(args: dict) -> str:
    """
    Create heatmap visualization of top DEGs with customizable colors

    Args:
        adata_path: Path to h5ad file with DEG results
        key: Key in adata.uns containing results (default: 'rank_genes_groups')
        n_genes: Number of top genes per group to show (default: 10)
        groupby: Column to group cells by (should match the one used in find_markers)
        save_path: Output path for plot (default: /tmp/deg_heatmap.png)
        figsize: Figure size as [width, height]
        show_gene_labels: Whether to show gene names
        cmap: Colormap for expression values ('viridis', 'RdBu_r', 'coolwarm', etc.)
        vmin: Minimum value for color scale
        vmax: Maximum value for color scale
        standard_scale: Standardize by 'var' (genes) or 'group'

    Returns:
        Path to saved plot
    """
    try:
        adata_path = args.get("adata_path", "/tmp/sc_umap_deg.h5ad")
        key = args.get("key", "rank_genes_groups")
        n_genes = args.get("n_genes", 10)
        groupby = args.get("groupby", "leiden")
        save_path = args.get("save_path", "/tmp/deg_heatmap.png")
        figsize = tuple(args.get("figsize", [12, 10]))
        show_gene_labels = args.get("show_gene_labels", True)
        cmap = args.get("cmap", "viridis")
        vmin = args.get("vmin")
        vmax = args.get("vmax")
        standard_scale = args.get("standard_scale")

        logger.info(f"🎨 Creating DEG heatmap...")

        # Load data
        adata = read_h5ad_compat(adata_path)

        if key not in adata.uns:
            raise ValueError(f"No DEG results found at adata.uns['{key}']\n{DEG_PALETTE_HELP}")

        # Build plot kwargs
        plot_kwargs = {
            'n_genes': n_genes,
            'key': key,
            'groupby': groupby,
            'show_gene_labels': show_gene_labels,
            'figsize': figsize,
            'show': False,
            'return_fig': True,
            'cmap': cmap
        }

        if vmin is not None:
            plot_kwargs['vmin'] = vmin
        if vmax is not None:
            plot_kwargs['vmax'] = vmax
        if standard_scale:
            plot_kwargs['standard_scale'] = standard_scale

        # Create heatmap using scanpy
        plot_kwargs.pop('return_fig', None)
        hm = sc.pl.rank_genes_groups_heatmap(adata, **plot_kwargs)

        # Force-adjust x-axis gene labels for readability
        n_groups = adata.obs[groupby].nunique()
        total_genes = n_genes * n_groups
        if total_genes <= 30:
            gene_fontsize = 11
        elif total_genes <= 50:
            gene_fontsize = 9
        elif total_genes <= 80:
            gene_fontsize = 7
        else:
            gene_fontsize = 5

        fig = plt.gcf()
        all_axes = fig.get_axes()
        # The main heatmap axis is typically the largest one
        for ax in all_axes:
            xlabels = [lbl.get_text() for lbl in ax.get_xticklabels()]
            if xlabels and len([l for l in xlabels if l.strip()]) > 2:
                ax.set_xticklabels(
                    xlabels,
                    fontsize=gene_fontsize,
                    rotation=90,
                    ha='center',
                    va='top'
                )
                ax.tick_params(axis='x', which='both', labelsize=gene_fontsize, pad=2)

        fig.subplots_adjust(bottom=0.22)
        fig.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close('all')

        logger.info(f"💾 Saved heatmap to {save_path}")

        return f"""
✅ DEG heatmap created successfully!

📊 Plot Details:
  • Top genes per group: {n_genes}
  • Groups: {groupby}
  • Figure size: {figsize}
  • Colormap: {cmap}

💾 Saved to: {save_path}
"""

    except Exception as e:
        logger.error(f"Error in sc_plot_deg_heatmap: {e}", exc_info=True)
        raise


async def sc_plot_deg_dotplot(args: dict) -> str:
    """
    Create dotplot visualization of top DEGs with customizable colors

    Args:
        adata_path: Path to h5ad file with DEG results
        key: Key in adata.uns containing results (default: 'rank_genes_groups')
        n_genes: Number of top genes per group to show (default: 5)
        groupby: Column to group cells by
        save_path: Output path for plot (default: /tmp/deg_dotplot.png)
        figsize: Figure size as [width, height]
        cmap: Colormap for expression ('Reds', 'viridis', 'Blues', etc.)
        dot_max: Maximum dot size (fraction, 0-1)
        dot_min: Minimum dot size (fraction, 0-1)
        vmin: Minimum value for color scale
        vmax: Maximum value for color scale
        standard_scale: Standardize by 'var' (genes) or 'group'

    Returns:
        Path to saved plot
    """
    try:
        adata_path = args.get("adata_path", "/tmp/sc_umap_deg.h5ad")
        key = args.get("key", "rank_genes_groups")
        n_genes = args.get("n_genes", 5)
        groupby = args.get("groupby", "leiden")
        save_path = args.get("save_path", "/tmp/deg_dotplot.png")
        figsize = tuple(args.get("figsize", [12, 8]))
        cmap = args.get("cmap", "Reds")
        dot_max = args.get("dot_max")
        dot_min = args.get("dot_min")
        vmin = args.get("vmin")
        vmax = args.get("vmax")
        standard_scale = args.get("standard_scale")

        logger.info(f"🎨 Creating DEG dotplot...")

        # Load data
        adata = read_h5ad_compat(adata_path)

        if key not in adata.uns:
            raise ValueError(f"No DEG results found at adata.uns['{key}']\n{DEG_PALETTE_HELP}")

        # Build plot kwargs
        plot_kwargs = {
            'n_genes': n_genes,
            'key': key,
            'groupby': groupby,
            'figsize': figsize,
            'show': False,
            'return_fig': True,
            'cmap': cmap
        }

        if dot_max is not None:
            plot_kwargs['dot_max'] = dot_max
        if dot_min is not None:
            plot_kwargs['dot_min'] = dot_min
        if vmin is not None:
            plot_kwargs['vmin'] = vmin
        if vmax is not None:
            plot_kwargs['vmax'] = vmax
        if standard_scale:
            plot_kwargs['standard_scale'] = standard_scale

        # Create dotplot
        dp = sc.pl.rank_genes_groups_dotplot(adata, **plot_kwargs)

        # Save figure - DotPlot object has its own savefig method
        if hasattr(dp, 'savefig'):
            dp.savefig(save_path, dpi=300, bbox_inches='tight')
        else:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close('all')

        logger.info(f"💾 Saved dotplot to {save_path}")

        return f"""
✅ DEG dotplot created successfully!

📊 Plot Details:
  • Top genes per group: {n_genes}
  • Groups: {groupby}
  • Figure size: {figsize}
  • Colormap: {cmap}

💾 Saved to: {save_path}
"""

    except Exception as e:
        logger.error(f"Error in sc_plot_deg_dotplot: {e}", exc_info=True)
        raise


async def sc_compare_groups(args: dict) -> str:
    """
    Compare two specific groups to find differentially expressed genes
    
    Args:
        adata_path: Path to h5ad file
        groupby: Column name containing groups
        group1: First group name (e.g., "Young", "Control")
        group2: Second group name (e.g., "Aged", "Treatment")
        method: Statistical test method
        n_genes: Number of top genes to return
        use_raw: Whether to use raw counts
        corr_method: Multiple testing correction method
        key_added: Key to store results in adata.uns
    
    Returns:
        Success message with comparison summary
    """
    try:
        adata_path = args.get("adata_path", "/tmp/sc_umap.h5ad")
        groupby = args.get("groupby")
        group1 = args.get("group1")
        group2 = args.get("group2")
        method = args.get("method", "wilcoxon")
        n_genes = args.get("n_genes", 100)
        use_raw = args.get("use_raw", True)
        corr_method = args.get("corr_method", "fdr_bh")
        # Map fdr_bh to benjamini-hochberg for scanpy compatibility
        if corr_method == "fdr_bh":
            corr_method = "benjamini-hochberg"
        key_added = args.get("key_added", f"deg_{group1}_vs_{group2}")
        
        if not groupby:
            raise ValueError("groupby parameter is required")
        if not group1 or not group2:
            raise ValueError("Both group1 and group2 are required")
        
        logger.info(f"🔍 Comparing {group1} vs {group2} in {groupby}")
        
        # Load data
        adata = read_h5ad_compat(adata_path)
        
        # Validate
        if groupby not in adata.obs.columns:
            raise ValueError(f"Column '{groupby}' not found in adata.obs")
        
        available_groups = adata.obs[groupby].unique().tolist()
        if group1 not in available_groups:
            raise ValueError(f"Group '{group1}' not found in {groupby}. Available: {available_groups}")
        if group2 not in available_groups:
            raise ValueError(f"Group '{group2}' not found in {groupby}. Available: {available_groups}")
        
        # Subset to only these two groups
        adata_subset = adata[adata.obs[groupby].isin([group1, group2])].copy()
        
        # Check if raw data exists
        if use_raw and adata_subset.raw is None:
            logger.warning("⚠️ No raw data found, using normalized data")
            use_raw = False
        
        # Run comparison
        logger.info(f"📊 Running {method} test...")
        sc.tl.rank_genes_groups(
            adata_subset,
            groupby=groupby,
            groups=[group1],  # Compare group1 vs rest (which is only group2)
            reference=group2,
            method=method,
            n_genes=n_genes,
            use_raw=use_raw,
            corr_method=corr_method,
            key_added=key_added
        )
        
        # Save results back to original adata
        adata.uns[key_added] = adata_subset.uns[key_added]
        
        output_path = adata_path.replace(".h5ad", f"_{key_added}.h5ad")
        adata.write_h5ad(output_path)
        logger.info(f"💾 Saved to {output_path}")
        
        # Get summary statistics
        result_df = sc.get.rank_genes_groups_df(adata_subset, group=group1, key=key_added)
        n_sig = len(result_df[result_df['pvals_adj'] < 0.05])
        
        # Get top upregulated and downregulated genes
        top_up = result_df[result_df['logfoldchanges'] > 0].head(5)
        top_down = result_df[result_df['logfoldchanges'] < 0].head(5)
        
        result_summary = f"""
✅ Group comparison completed!

📋 Comparison Details:
  • Group 1: {group1} ({(adata_subset.obs[groupby] == group1).sum():,} cells)
  • Group 2: {group2} ({(adata_subset.obs[groupby] == group2).sum():,} cells)
  • Grouping column: {groupby}
  • Method: {method}
  • Correction: {corr_method}
  
💾 Results saved to:
  • {output_path}
  • DEG results stored in adata.uns['{key_added}']

📊 Summary Statistics:
  • Total genes tested: {len(result_df):,}
  • Significant genes (padj < 0.05): {n_sig:,}
  • Upregulated in {group1}: {len(result_df[(result_df['pvals_adj'] < 0.05) & (result_df['logfoldchanges'] > 0)]):,}
  • Downregulated in {group1}: {len(result_df[(result_df['pvals_adj'] < 0.05) & (result_df['logfoldchanges'] < 0)]):,}

🔝 Top 5 Upregulated in {group1}:
{top_up[['names', 'logfoldchanges', 'pvals_adj']].to_string(index=False)}

🔻 Top 5 Downregulated in {group1}:
{top_down[['names', 'logfoldchanges', 'pvals_adj']].to_string(index=False)}

💡 Next steps:
  1. Use sc_get_deg_results(key='{key_added}') to view more genes
  2. Use sc_export_deg(key='{key_added}') to export results
  3. Use sc_plot_deg_heatmap(key='{key_added}') for visualization
"""
        return result_summary
        
    except Exception as e:
        logger.error(f"Error in sc_compare_groups: {e}", exc_info=True)
        raise


async def sc_find_markers_vs_rest(args: dict) -> str:
    """
    Find marker genes for specific groups vs all other cells (one-vs-rest)
    
    Args:
        adata_path: Path to h5ad file
        groupby: Column name to group by
        groups: List of specific groups to analyze (optional, analyzes all if not specified)
        reference: Reference group name (optional, uses 'rest' if not specified)
        method: Statistical test method
        n_genes: Number of top genes per group
        use_raw: Whether to use raw counts
        corr_method: Multiple testing correction method
        key_added: Key to store results in adata.uns
    
    Returns:
        Success message with summary statistics
    """
    try:
        adata_path = args.get("adata_path", "/tmp/sc_umap.h5ad")
        groupby = args.get("groupby", "leiden")
        groups = args.get("groups")  # List of specific groups, e.g., ["0", "1", "2"]
        reference = args.get("reference", "rest")
        method = args.get("method", "wilcoxon")
        n_genes = args.get("n_genes", 100)
        use_raw = args.get("use_raw", True)
        corr_method = args.get("corr_method", "fdr_bh")
        # Map fdr_bh to benjamini-hochberg for scanpy compatibility
        if corr_method == "fdr_bh":
            corr_method = "benjamini-hochberg"
        key_added = args.get("key_added", "rank_genes_groups_vs_rest")
        
        logger.info(f"🔍 Finding markers from {adata_path}")
        
        # Load data
        adata = read_h5ad_compat(adata_path)
        
        # Validate groupby column
        if groupby not in adata.obs.columns:
            raise ValueError(f"Column '{groupby}' not found in adata.obs")
        
        available_groups = adata.obs[groupby].unique().tolist()
        
        # Validate groups if specified
        if groups:
            for grp in groups:
                if grp not in available_groups:
                    raise ValueError(f"Group '{grp}' not found in {groupby}. Available: {available_groups}")
        
        # Check if raw data exists
        if use_raw and adata.raw is None:
            logger.warning("⚠️ No raw data found, using normalized data")
            use_raw = False
        
        # Run differential expression analysis
        logger.info(f"📊 Computing DEGs using {method} test (one-vs-rest)...")
        sc.tl.rank_genes_groups(
            adata,
            groupby=groupby,
            groups=groups,  # Specific groups or None for all
            reference=reference,  # 'rest' or specific group name
            method=method,
            n_genes=n_genes,
            use_raw=use_raw,
            corr_method=corr_method,
            key_added=key_added
        )
        
        # Save results
        output_path = adata_path.replace(".h5ad", f"_{key_added}.h5ad")
        adata.write_h5ad(output_path)
        logger.info(f"💾 Saved to {output_path}")
        
        # Generate summary
        analyzed_groups = groups if groups else available_groups
        n_groups = len(analyzed_groups)
        
        result_summary = f"""
✅ One-vs-rest marker analysis completed!

📋 Analysis Parameters:
  • Grouping: {groupby}
  • Groups analyzed: {n_groups} {f"({', '.join(map(str, analyzed_groups[:5]))}" + ("..." if len(analyzed_groups) > 5 else "") + ")" if analyzed_groups else ""}
  • Reference: {reference}
  • Method: {method}
  • Top genes per group: {n_genes}
  • Use raw counts: {use_raw}
  • Correction method: {corr_method}
  
💾 Results saved to:
  • {output_path}
  • DEG results stored in adata.uns['{key_added}']

📊 Summary Statistics:
  • Total cells: {adata.n_obs:,}
  • Total genes tested: {adata.n_vars:,}
  • Groups analyzed: {n_groups}
  • Genes per group: {n_genes}
  
💡 Next steps:
  1. Use sc_get_deg_results(key='{key_added}') to view top genes
  2. Use sc_export_deg(key='{key_added}') to save results
  3. Use sc_plot_deg_heatmap(key='{key_added}') for visualization
"""
        return result_summary
        
    except Exception as e:
        logger.error(f"Error in sc_find_markers_vs_rest: {e}", exc_info=True)
        raise


# ============================================================================
# Pseudobulk DEG Analysis (DESeq2-based)
# ============================================================================

async def sc_pseudobulk_deg(args: dict) -> str:
    """
    Pseudobulk differential expression analysis using DESeq2

    Aggregates single-cell counts by sample, then applies DESeq2 for
    statistically robust differential expression analysis that properly
    accounts for biological replicates.

    Args:
        adata_path: Path to h5ad file
        sample_key: Column containing sample/replicate IDs (REQUIRED)
        condition_key: Column containing condition to compare (REQUIRED)
        condition1: First condition (e.g., "Control")
        condition2: Second condition (e.g., "Treatment")
        cell_type_key: Optional - analyze within specific cell types
        cell_type: Optional - specific cell type to analyze
        min_cells: Minimum cells per sample to include (default: 10)
        min_counts: Minimum total counts per gene (default: 10)
        output_dir: Directory to save results

    Returns:
        DEG results summary with statistics
    """
    try:
        adata_path = args.get("adata_path", "/tmp/sc_umap.h5ad")
        sample_key = args.get("sample_key")
        condition_key = args.get("condition_key")
        condition1 = args.get("condition1")
        condition2 = args.get("condition2")
        cell_type_key = args.get("cell_type_key")
        cell_type = args.get("cell_type")
        min_cells = args.get("min_cells", 10)
        min_counts = args.get("min_counts", 10)
        output_dir = args.get("output_dir", "/tmp/pseudobulk_results")

        # Validate required parameters
        if not sample_key:
            return "❌ Error: sample_key required (column with sample/replicate IDs)"
        if not condition_key:
            return "❌ Error: condition_key required (column with conditions to compare)"
        if not condition1 or not condition2:
            return "❌ Error: Both condition1 and condition2 required"

        logger.info(f"🧬 Running pseudobulk DEG analysis...")

        # Load data
        adata = read_h5ad_compat(adata_path)

        # Validate columns
        if sample_key not in adata.obs.columns:
            return f"❌ Error: '{sample_key}' not found. Available: {list(adata.obs.columns)[:15]}"
        if condition_key not in adata.obs.columns:
            return f"❌ Error: '{condition_key}' not found. Available: {list(adata.obs.columns)[:15]}"

        # Validate conditions
        available_conditions = adata.obs[condition_key].unique().tolist()
        if condition1 not in available_conditions:
            return f"❌ Error: '{condition1}' not found in {condition_key}. Available: {available_conditions}"
        if condition2 not in available_conditions:
            return f"❌ Error: '{condition2}' not found in {condition_key}. Available: {available_conditions}"

        # Subset to cell type if specified
        if cell_type_key and cell_type:
            if cell_type_key not in adata.obs.columns:
                return f"❌ Error: '{cell_type_key}' not found"
            adata = adata[adata.obs[cell_type_key] == cell_type].copy()
            if adata.n_obs == 0:
                return f"❌ Error: No cells found for {cell_type_key}={cell_type}"
            logger.info(f"Subset to {cell_type}: {adata.n_obs:,} cells")

        # Filter to conditions of interest
        adata = adata[adata.obs[condition_key].isin([condition1, condition2])].copy()

        # Get raw counts (required for DESeq2)
        if adata.raw is not None:
            count_matrix = adata.raw.X
            gene_names = adata.raw.var_names
        else:
            count_matrix = adata.X
            gene_names = adata.var_names
            logger.warning("⚠️ Using normalized data (raw counts preferred for DESeq2)")

        # Convert sparse matrix if needed
        if hasattr(count_matrix, 'toarray'):
            count_matrix = count_matrix.toarray()

        # Create pseudobulk by summing counts per sample
        samples = adata.obs[sample_key].unique()
        pseudobulk_data = []
        sample_metadata = []
        excluded_samples = []

        for sample in samples:
            mask = adata.obs[sample_key] == sample
            n_cells = mask.sum()

            if n_cells < min_cells:
                excluded_samples.append((sample, n_cells))
                continue

            # Sum counts for this sample
            sample_counts = count_matrix[mask].sum(axis=0)
            if hasattr(sample_counts, 'A1'):
                sample_counts = sample_counts.A1
            pseudobulk_data.append(sample_counts)

            # Get condition for this sample
            condition = adata.obs.loc[mask, condition_key].iloc[0]
            sample_metadata.append({
                'sample': sample,
                'condition': condition,
                'n_cells': n_cells
            })

        if len(pseudobulk_data) < 4:
            return f"""❌ Error: Not enough samples for DESeq2 analysis!

Found {len(pseudobulk_data)} samples (need at least 2 per condition)
Excluded samples (< {min_cells} cells): {excluded_samples}

💡 Tips:
   - Reduce min_cells parameter
   - Check sample_key column for correct sample grouping
   - Ensure sufficient biological replicates"""

        # Create count matrix and metadata DataFrame
        count_df = pd.DataFrame(
            np.array(pseudobulk_data),
            index=[m['sample'] for m in sample_metadata],
            columns=gene_names
        ).T  # Genes as rows, samples as columns

        meta_df = pd.DataFrame(sample_metadata)
        meta_df = meta_df.set_index('sample')

        # Filter low-count genes
        gene_counts = count_df.sum(axis=1)
        count_df = count_df[gene_counts >= min_counts]
        n_genes_filtered = len(count_df)

        # Check samples per condition
        n_cond1 = (meta_df['condition'] == condition1).sum()
        n_cond2 = (meta_df['condition'] == condition2).sum()

        if n_cond1 < 2 or n_cond2 < 2:
            return f"""❌ Error: Need at least 2 samples per condition!

{condition1}: {n_cond1} samples
{condition2}: {n_cond2} samples

💡 Pseudobulk requires biological replicates for statistical validity."""

        # Create output directory
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # Run DESeq2
        try:
            from pydeseq2.dds import DeseqDataSet
            from pydeseq2.ds import DeseqStats

            logger.info("Running DESeq2...")

            # Ensure counts are integers
            count_df = count_df.round().astype(int)

            # Create DESeq2 dataset
            dds = DeseqDataSet(
                counts=count_df.T,  # samples x genes
                metadata=meta_df,
                design_factors="condition",
                refit_cooks=True
            )

            # Run DESeq2 pipeline
            dds.deseq2()

            # Get results for condition comparison
            stat_res = DeseqStats(dds, contrast=["condition", condition1, condition2])
            stat_res.summary()

            # Get results DataFrame
            results_df = stat_res.results_df.copy()
            results_df['gene'] = results_df.index
            results_df = results_df.reset_index(drop=True)

            # Sort by adjusted p-value
            results_df = results_df.sort_values('padj')

            # Count significant genes
            sig_genes = results_df[results_df['padj'] < 0.05]
            n_up = len(sig_genes[sig_genes['log2FoldChange'] > 0])
            n_down = len(sig_genes[sig_genes['log2FoldChange'] < 0])

            # Save results
            results_path = f"{output_dir}/pseudobulk_deg_{condition1}_vs_{condition2}.csv"
            results_df.to_csv(results_path, index=False)

            # Save significant genes
            sig_path = f"{output_dir}/pseudobulk_significant.csv"
            sig_genes.to_csv(sig_path, index=False)

            # Get top genes for display
            top_up = results_df[(results_df['padj'] < 0.05) & (results_df['log2FoldChange'] > 0)].head(10)
            top_down = results_df[(results_df['padj'] < 0.05) & (results_df['log2FoldChange'] < 0)].head(10)

            # Sample summary
            sample_summary = "\n".join([
                f"   • {row['sample']}: {row['condition']} ({row['n_cells']:,} cells)"
                for _, row in meta_df.reset_index().iterrows()
            ])

            result = f"""
✅ Pseudobulk DEG Analysis Complete!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 ANALYSIS SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔬 Comparison: {condition1} vs {condition2}
{f'🧫 Cell type: {cell_type}' if cell_type else '🧫 Cell types: All'}
📦 Method: DESeq2 (pseudobulk)

📈 Samples:
{sample_summary}

📊 Statistics:
   • Total samples: {len(meta_df)}
   • {condition1}: {n_cond1} samples
   • {condition2}: {n_cond2} samples
   • Genes tested: {n_genes_filtered:,}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 DEG RESULTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📈 Significant genes (padj < 0.05): {len(sig_genes):,}
   • Upregulated in {condition1}: {n_up:,}
   • Downregulated in {condition1}: {n_down:,}

🔝 Top Upregulated in {condition1}:
{top_up[['gene', 'log2FoldChange', 'padj']].head(5).to_string(index=False) if len(top_up) > 0 else '   (none)'}

🔻 Top Downregulated in {condition1}:
{top_down[['gene', 'log2FoldChange', 'padj']].head(5).to_string(index=False) if len(top_down) > 0 else '   (none)'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💾 OUTPUT FILES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   • Full results: {results_path}
   • Significant only: {sig_path}

💡 Next steps:
   1. sc_plot_volcano for volcano plot
   2. sc_plot_ma for MA plot
   3. Pathway/GO enrichment analysis on significant genes
"""
            return result

        except ImportError:
            return """❌ Error: pydeseq2 not installed!

📦 Install with:
   pip install pydeseq2

💡 pydeseq2 is a Python implementation of DESeq2 for differential expression analysis."""

    except Exception as e:
        logger.error(f"Error in sc_pseudobulk_deg: {e}", exc_info=True)
        return f"❌ Error: {e}"


# ============================================================================
# Volcano Plot
# ============================================================================

async def sc_plot_volcano(args: dict) -> str:
    """
    Create volcano plot for DEG visualization

    Shows -log10(p-value) vs log2 fold change with significance thresholds.

    Args:
        deg_results: Path to DEG results CSV (from pseudobulk or export)
        adata_path: Alternative - path to h5ad with DEG results
        deg_key: Key in adata.uns for DEG results
        group: Group to plot (for scanpy results)
        pval_col: Column name for p-values (default: 'padj' or 'pvals_adj')
        logfc_col: Column name for log fold change (default: 'log2FoldChange' or 'logfoldchanges')
        gene_col: Column name for gene names (default: 'gene' or 'names')
        pval_threshold: P-value threshold for significance (default: 0.05)
        logfc_threshold: Log2 fold change threshold (default: 1.0)
        top_n_labels: Number of top genes to label (default: 10)
        save_path: Output path for plot
        figsize: Figure size as [width, height]
        title: Plot title

    Returns:
        Path to saved plot
    """
    try:
        deg_results = args.get("deg_results")
        adata_path = args.get("adata_path")
        deg_key = args.get("deg_key", "rank_genes_groups")
        group = args.get("group")
        pval_threshold = args.get("pval_threshold", 0.05)
        logfc_threshold = args.get("logfc_threshold", 1.0)
        top_n_labels = args.get("top_n_labels", 10)
        save_path = args.get("save_path", "/tmp/volcano_plot.png")
        figsize = args.get("figsize", [10, 8])
        title = args.get("title")

        import matplotlib
        matplotlib.use('Agg')

        # Load DEG results
        if deg_results and Path(deg_results).exists():
            # Load from CSV
            df = pd.read_csv(deg_results)

            # Auto-detect column names
            pval_col = None
            logfc_col = None
            gene_col = None

            for col in df.columns:
                col_lower = col.lower()
                if 'padj' in col_lower or 'pvals_adj' in col_lower or 'pvalue' in col_lower:
                    pval_col = col
                if 'log2foldchange' in col_lower or 'logfoldchange' in col_lower or 'logfc' in col_lower:
                    logfc_col = col
                if col_lower in ['gene', 'names', 'gene_name', 'symbol']:
                    gene_col = col

            if not pval_col or not logfc_col:
                return f"""❌ Could not auto-detect columns.
Available columns: {list(df.columns)}

Expected columns like:
   - P-value: padj, pvals_adj, pvalue
   - Log FC: log2FoldChange, logfoldchanges
   - Gene: gene, names"""

            if not gene_col:
                gene_col = df.columns[0]  # Assume first column is gene names

        elif adata_path:
            # Load from AnnData
            adata = read_h5ad_compat(adata_path)

            if deg_key not in adata.uns:
                return f"❌ DEG results not found at adata.uns['{deg_key}']"

            df = sc.get.rank_genes_groups_df(adata, group=group, key=deg_key)
            pval_col = 'pvals_adj'
            logfc_col = 'logfoldchanges'
            gene_col = 'names'
        else:
            return "❌ Provide either deg_results (CSV path) or adata_path"

        # Remove NA values
        df = df.dropna(subset=[pval_col, logfc_col])

        # Calculate -log10(pval)
        df['neg_log10_pval'] = -np.log10(df[pval_col].clip(lower=1e-300))

        # Categorize genes
        df['significance'] = 'Not Significant'
        df.loc[(df[pval_col] < pval_threshold) & (df[logfc_col] > logfc_threshold), 'significance'] = 'Up'
        df.loc[(df[pval_col] < pval_threshold) & (df[logfc_col] < -logfc_threshold), 'significance'] = 'Down'

        # Count categories
        n_up = (df['significance'] == 'Up').sum()
        n_down = (df['significance'] == 'Down').sum()
        n_ns = (df['significance'] == 'Not Significant').sum()

        # Get custom colors if provided
        up_color = args.get("up_color", "#e74c3c")
        down_color = args.get("down_color", "#3498db")
        ns_color = args.get("ns_color", "#95a5a6")
        point_size = args.get("point_size", 20)
        alpha = args.get("alpha", 0.6)

        # Create plot
        fig, ax = plt.subplots(figsize=tuple(figsize))

        colors = {'Up': up_color, 'Down': down_color, 'Not Significant': ns_color}

        for sig, color in colors.items():
            mask = df['significance'] == sig
            ax.scatter(
                df.loc[mask, logfc_col],
                df.loc[mask, 'neg_log10_pval'],
                c=color,
                label=f"{sig} ({mask.sum():,})",
                alpha=alpha,
                s=point_size
            )

        # Add threshold lines
        ax.axhline(y=-np.log10(pval_threshold), color='gray', linestyle='--', linewidth=1, alpha=0.5)
        ax.axvline(x=logfc_threshold, color='gray', linestyle='--', linewidth=1, alpha=0.5)
        ax.axvline(x=-logfc_threshold, color='gray', linestyle='--', linewidth=1, alpha=0.5)

        # Label top genes
        if top_n_labels > 0:
            # Get top significant genes
            sig_df = df[df['significance'] != 'Not Significant'].copy()
            sig_df['score'] = sig_df['neg_log10_pval'] * abs(sig_df[logfc_col])
            top_genes = sig_df.nlargest(top_n_labels, 'score')

            texts = []
            for _, row in top_genes.iterrows():
                texts.append(ax.annotate(
                    row[gene_col],
                    (row[logfc_col], row['neg_log10_pval']),
                    fontsize=8,
                    alpha=0.8
                ))

            try:
                from adjustText import adjust_text
                adjust_text(texts, arrowprops=dict(arrowstyle='-', color='gray', alpha=0.5))
            except Exception:
                logger.info("adjustText unavailable or failed; leaving direct volcano labels in place")

        ax.set_xlabel('Log2 Fold Change', fontsize=12)
        ax.set_ylabel('-Log10(Adjusted P-value)', fontsize=12)

        if title:
            ax.set_title(title, fontsize=14)
        else:
            ax.set_title('Volcano Plot', fontsize=14)

        ax.legend(loc='upper right')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()

        return f"""
✅ Volcano Plot Created!

📊 Summary:
   • Upregulated (log2FC > {logfc_threshold}, padj < {pval_threshold}): {n_up:,}
   • Downregulated (log2FC < -{logfc_threshold}, padj < {pval_threshold}): {n_down:,}
   • Not significant: {n_ns:,}
   • Top {top_n_labels} genes labeled

🎨 Colors: Up={up_color}, Down={down_color}, NS={ns_color}

💾 Saved: {save_path}
"""

    except Exception as e:
        logger.error(f"Error in sc_plot_volcano: {e}", exc_info=True)
        return f"❌ Error: {e}\n{DEG_PALETTE_HELP}"


# ============================================================================
# MA Plot
# ============================================================================

async def sc_plot_ma(args: dict) -> str:
    """
    Create MA plot for DEG visualization

    Shows log2 fold change vs mean expression (M vs A plot).

    Args:
        deg_results: Path to DEG results CSV
        adata_path: Alternative - path to h5ad with DEG results
        deg_key: Key in adata.uns for DEG results
        group: Group to plot (for scanpy results)
        pval_threshold: P-value threshold for significance (default: 0.05)
        logfc_threshold: Log2 fold change threshold for highlighting (default: 1.0)
        top_n_labels: Number of top genes to label (default: 10)
        save_path: Output path for plot
        figsize: Figure size as [width, height]
        title: Plot title

    Returns:
        Path to saved plot
    """
    try:
        deg_results = args.get("deg_results")
        adata_path = args.get("adata_path")
        deg_key = args.get("deg_key", "rank_genes_groups")
        group = args.get("group")
        pval_threshold = args.get("pval_threshold", 0.05)
        logfc_threshold = args.get("logfc_threshold", 1.0)
        top_n_labels = args.get("top_n_labels", 10)
        save_path = args.get("save_path", "/tmp/ma_plot.png")
        figsize = args.get("figsize", [10, 8])
        title = args.get("title")

        import matplotlib
        matplotlib.use('Agg')

        # Load DEG results
        if deg_results and Path(deg_results).exists():
            df = pd.read_csv(deg_results)

            # Auto-detect columns
            pval_col = None
            logfc_col = None
            mean_col = None
            gene_col = None

            for col in df.columns:
                col_lower = col.lower()
                if 'padj' in col_lower or 'pvals_adj' in col_lower:
                    pval_col = col
                if 'log2foldchange' in col_lower or 'logfoldchange' in col_lower:
                    logfc_col = col
                if 'basemean' in col_lower or 'mean' in col_lower:
                    mean_col = col
                if col_lower in ['gene', 'names', 'gene_name']:
                    gene_col = col

            if not pval_col or not logfc_col:
                return f"❌ Could not detect required columns. Available: {list(df.columns)}"

            if not gene_col:
                gene_col = df.columns[0]

        elif adata_path:
            adata = read_h5ad_compat(adata_path)

            if deg_key not in adata.uns:
                return f"❌ DEG results not found at adata.uns['{deg_key}']"

            df = sc.get.rank_genes_groups_df(adata, group=group, key=deg_key)
            pval_col = 'pvals_adj'
            logfc_col = 'logfoldchanges'
            gene_col = 'names'
            mean_col = None  # Scanpy doesn't include mean expression by default
        else:
            return "❌ Provide either deg_results (CSV path) or adata_path"

        # Remove NA values
        df = df.dropna(subset=[pval_col, logfc_col])

        # Calculate mean expression if not available
        if mean_col is None or mean_col not in df.columns:
            # Use scores or create synthetic A values based on rank
            if 'scores' in df.columns:
                df['A'] = np.abs(df['scores'])
            else:
                df['A'] = np.arange(len(df))[::-1]  # Rank-based
            mean_col = 'A'

        # Log transform mean if needed
        if df[mean_col].min() >= 0:
            df['log_mean'] = np.log10(df[mean_col].clip(lower=0.1))
        else:
            df['log_mean'] = df[mean_col]

        # Categorize genes
        df['significance'] = 'Not Significant'
        df.loc[(df[pval_col] < pval_threshold) & (df[logfc_col] > logfc_threshold), 'significance'] = 'Up'
        df.loc[(df[pval_col] < pval_threshold) & (df[logfc_col] < -logfc_threshold), 'significance'] = 'Down'

        n_up = (df['significance'] == 'Up').sum()
        n_down = (df['significance'] == 'Down').sum()

        # Get custom colors if provided
        up_color = args.get("up_color", "#e74c3c")
        down_color = args.get("down_color", "#3498db")
        ns_color = args.get("ns_color", "#95a5a6")
        point_size = args.get("point_size", 20)
        alpha = args.get("alpha", 0.6)

        # Create plot
        fig, ax = plt.subplots(figsize=tuple(figsize))

        colors = {'Up': up_color, 'Down': down_color, 'Not Significant': ns_color}

        for sig, color in colors.items():
            mask = df['significance'] == sig
            ax.scatter(
                df.loc[mask, 'log_mean'],
                df.loc[mask, logfc_col],
                c=color,
                label=f"{sig} ({mask.sum():,})",
                alpha=alpha,
                s=point_size
            )

        # Add threshold lines
        ax.axhline(y=0, color='gray', linestyle='-', linewidth=1, alpha=0.5)
        ax.axhline(y=logfc_threshold, color='gray', linestyle='--', linewidth=1, alpha=0.3)
        ax.axhline(y=-logfc_threshold, color='gray', linestyle='--', linewidth=1, alpha=0.3)

        # Label top genes
        if top_n_labels > 0:
            sig_df = df[df['significance'] != 'Not Significant'].copy()
            sig_df['score'] = abs(sig_df[logfc_col])
            top_genes = sig_df.nlargest(top_n_labels, 'score')

            for _, row in top_genes.iterrows():
                ax.annotate(
                    row[gene_col],
                    (row['log_mean'], row[logfc_col]),
                    fontsize=8,
                    alpha=0.8,
                    xytext=(5, 5),
                    textcoords='offset points'
                )

        ax.set_xlabel('Log10 Mean Expression', fontsize=12)
        ax.set_ylabel('Log2 Fold Change', fontsize=12)

        if title:
            ax.set_title(title, fontsize=14)
        else:
            ax.set_title('MA Plot', fontsize=14)

        ax.legend(loc='upper right')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()

        return f"""
✅ MA Plot Created!

📊 Summary:
   • Upregulated: {n_up:,}
   • Downregulated: {n_down:,}
   • Thresholds: |log2FC| > {logfc_threshold}, padj < {pval_threshold}

🎨 Colors: Up={up_color}, Down={down_color}, NS={ns_color}

💾 Saved: {save_path}
"""

    except Exception as e:
        logger.error(f"Error in sc_plot_ma: {e}", exc_info=True)
        return f"❌ Error: {e}\n{DEG_PALETTE_HELP}"
