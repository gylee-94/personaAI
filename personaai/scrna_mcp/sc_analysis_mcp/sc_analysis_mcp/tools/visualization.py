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

"""Phase 4: Visualization tools"""
import logging
from ..h5ad_compat import read_h5ad_compat

logger = logging.getLogger("sc-analysis-mcp.visualization")

# =============================================================================
# Supported Color Palettes Reference
# =============================================================================
#
# CONTINUOUS COLORMAPS (for gene expression, numeric values):
#   - Sequential: 'viridis', 'plasma', 'inferno', 'magma', 'cividis'
#                 'Blues', 'Greens', 'Reds', 'Purples', 'Oranges', 'Greys'
#                 'YlOrRd', 'YlOrBr', 'YlGnBu', 'PuBuGn', 'BuPu', 'RdPu'
#   - Diverging:  'RdBu', 'RdYlBu', 'RdYlGn', 'PiYG', 'PRGn', 'BrBG', 'coolwarm', 'seismic'
#
# CATEGORICAL PALETTES (for clusters, cell types):
#   - Qualitative: 'tab10', 'tab20', 'tab20b', 'tab20c', 'Set1', 'Set2', 'Set3',
#                  'Paired', 'Accent', 'Dark2', 'Pastel1', 'Pastel2'
#   - Scanpy:      'scanpy default' (uses scanpy's built-in palette)
#
# CUSTOM COLORS:
#   - List of hex colors: ['#FF0000', '#00FF00', '#0000FF']
#   - List of named colors: ['red', 'green', 'blue']
#   - Dict mapping categories to colors: {'T_cell': '#FF0000', 'B_cell': '#00FF00'}
# =============================================================================

PALETTE_HELP = """
💡 Available color options:

📊 Continuous (for gene expression):
   viridis, plasma, inferno, magma, cividis
   Blues, Greens, Reds, YlOrRd, RdBu, coolwarm

🎨 Categorical (for clusters/cell types):
   tab10, tab20, Set1, Set2, Set3, Paired, Dark2

🔧 Custom:
   - Hex list: ['#FF5733', '#33FF57', '#3357FF']
   - Named colors: ['red', 'blue', 'green']
   - Dict: {'cluster_0': '#FF0000', 'cluster_1': '#00FF00'}
"""

async def sc_plot_umap(arguments: dict) -> str:
    """Plot UMAP colored by metadata or gene expression with customizable colors"""
    adata_path = arguments.get("adata_path", "/tmp/sc_umap.h5ad")
    color = arguments.get("color", "leiden")
    save_path = arguments.get("save_path")
    palette = arguments.get("palette")  # For categorical: 'tab20', 'Set1', list of colors, or dict
    cmap = arguments.get("cmap")  # For continuous: 'viridis', 'plasma', 'RdBu', etc.
    vmin = arguments.get("vmin")  # Min value for continuous colormap
    vmax = arguments.get("vmax")  # Max value for continuous colormap
    vcenter = arguments.get("vcenter")  # Center value for diverging colormaps

    try:
        import scanpy as sc
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        # Set larger font sizes (3x larger than default)
        plt.rcParams['font.size'] = 36
        plt.rcParams['axes.labelsize'] = 42
        plt.rcParams['axes.titlesize'] = 45
        plt.rcParams['xtick.labelsize'] = 33
        plt.rcParams['ytick.labelsize'] = 33
        plt.rcParams['legend.fontsize'] = 36
        plt.rcParams['legend.title_fontsize'] = 39

        adata = read_h5ad_compat(adata_path)

        # Validate color parameter
        is_gene = False
        if isinstance(color, str):
            if color not in adata.obs.columns and color not in adata.var_names:
                avail_cols = list(adata.obs.columns)[:10]
                return f"❌ Column/gene '{color}' not found.\nAvailable obs columns: {avail_cols}\n{PALETTE_HELP}"
            is_gene = color in adata.var_names

        # Set save path
        if save_path is None:
            color_name = color.replace(' ', '_') if isinstance(color, str) else 'multi'
            save_path = f"/tmp/umap_{color_name}.png"

        # Determine color settings
        plot_kwargs = {
            'show': False,
            'size': 180,
            'legend_fontsize': 36,
            'legend_fontweight': 'normal',
            'frameon': False
        }

        # Handle gene expression (continuous) vs categorical coloring
        if is_gene or (isinstance(color, str) and color in adata.obs.columns and
                       adata.obs[color].dtype in ['float64', 'float32', 'int64', 'int32']):
            # Continuous coloring - use cmap
            if cmap:
                plot_kwargs['cmap'] = cmap
            else:
                plot_kwargs['cmap'] = 'viridis'  # Default for expression

            if vmin is not None:
                plot_kwargs['vmin'] = vmin
            if vmax is not None:
                plot_kwargs['vmax'] = vmax
            if vcenter is not None:
                plot_kwargs['vcenter'] = vcenter
        else:
            # Categorical coloring - use palette
            if palette:
                # Handle dict, list, or string palette
                if isinstance(palette, dict):
                    plot_kwargs['palette'] = palette
                elif isinstance(palette, list):
                    plot_kwargs['palette'] = palette
                else:
                    plot_kwargs['palette'] = palette
            # If no palette specified, let scanpy use default

        # Plot with larger figure and cell size
        fig, ax = plt.subplots(figsize=(22, 20))
        sc.pl.umap(adata, color=color, ax=ax, **plot_kwargs)

        # Make plot square and increase legend marker size
        ax.set_aspect('equal', adjustable='box')
        legend = ax.get_legend()
        if legend:
            for handle in legend.legend_handles:
                handle.set_sizes([500])

        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()

        # Generate summary
        color_info = ""
        if palette:
            color_info = f"\n🎨 Palette: {palette if isinstance(palette, str) else 'custom'}"
        elif cmap:
            color_info = f"\n🎨 Colormap: {cmap}"

        if isinstance(color, str) and color in adata.obs.columns:
            counts = adata.obs[color].value_counts()
            n_groups = len(counts)
            count_str = "\n".join([f"   {g}: {c:,}" for g, c in counts.head(10).items()])

            result = f"""🗺️ UMAP Plot Created!
📊 Colored by: {color}
🎨 Number of groups: {n_groups}{color_info}
📈 Distribution:
{count_str}
💾 Saved: {save_path}"""
        else:
            result = f"""🗺️ UMAP Plot Created!
📊 Colored by: {color}{color_info}
💾 Saved: {save_path}"""

        return result

    except Exception as e:
        logger.error(f"Plot error: {e}", exc_info=True)
        return f"❌ {e}\n{PALETTE_HELP}"


async def sc_plot_cell_proportions(arguments: dict) -> str:
    """Analyze cell type proportions across conditions with Chi-square test"""
    adata_path = arguments.get("adata_path", "/tmp/sc_umap.h5ad")
    cell_type_column = arguments.get("cell_type_column")
    condition_column = arguments.get("condition_column")
    save_path = arguments.get("save_path", "/tmp/cell_proportions.png")
    plot_type = arguments.get("plot_type", "stacked_bar")  # stacked_bar, heatmap, line
    normalize = arguments.get("normalize", True)
    palette = arguments.get("palette", "tab20")  # For stacked_bar, line: 'tab20', 'Set1', etc.
    cmap = arguments.get("cmap", "YlOrRd")  # For heatmap: 'viridis', 'RdBu', etc.
    colors = arguments.get("colors")  # Custom color list for specific cell types

    try:
        import scanpy as sc
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import pandas as pd
        from scipy.stats import chi2_contingency

        adata = read_h5ad_compat(adata_path)

        # Validate columns
        if not cell_type_column or cell_type_column not in adata.obs.columns:
            return f"❌ '{cell_type_column}' not found in obs columns\n{PALETTE_HELP}"

        if not condition_column or condition_column not in adata.obs.columns:
            return f"❌ '{condition_column}' not found in obs columns"

        # Create contingency table
        ct_table = pd.crosstab(
            adata.obs[condition_column],
            adata.obs[cell_type_column]
        )

        # Chi-square test
        chi2, pval, dof, expected = chi2_contingency(ct_table)

        # Normalize if requested
        if normalize:
            ct_table_norm = ct_table.div(ct_table.sum(axis=1), axis=0) * 100
        else:
            ct_table_norm = ct_table

        # Handle custom colors
        color_param = None
        if colors:
            if isinstance(colors, list):
                color_param = colors
            elif isinstance(colors, dict):
                # Map colors to columns in order
                color_param = [colors.get(col, '#808080') for col in ct_table_norm.columns]

        # Plot
        fig, ax = plt.subplots(figsize=(12, 6))

        if plot_type == "stacked_bar":
            if color_param:
                ct_table_norm.plot(
                    kind='bar', stacked=True, ax=ax,
                    color=color_param, width=0.8
                )
            else:
                ct_table_norm.plot(
                    kind='bar', stacked=True, ax=ax,
                    colormap=palette, width=0.8
                )
            ax.set_ylabel('Proportion (%)' if normalize else 'Cell count')
            ax.legend(
                bbox_to_anchor=(1.05, 1),
                loc='upper left',
                title=cell_type_column
            )

        elif plot_type == "heatmap":
            import seaborn as sns
            sns.heatmap(
                ct_table_norm.T, annot=True, fmt='.1f',
                cmap=cmap, ax=ax,
                cbar_kws={'label': '% of cells' if normalize else 'Cell count'}
            )
            ax.set_xlabel(condition_column)
            ax.set_ylabel(cell_type_column)

        elif plot_type == "line":
            # Get colors from palette
            if color_param:
                line_colors = color_param
            else:
                cmap_obj = plt.get_cmap(palette)
                n_types = len(ct_table_norm.columns)
                line_colors = [cmap_obj(i / n_types) for i in range(n_types)]

            for i, col in enumerate(ct_table_norm.columns):
                ax.plot(
                    ct_table_norm.index, ct_table_norm[col],
                    marker='o', label=col, linewidth=2,
                    color=line_colors[i] if i < len(line_colors) else None
                )
            ax.set_ylabel('Proportion (%)' if normalize else 'Cell count')
            ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
            ax.grid(True, alpha=0.3)

        ax.set_xlabel(condition_column)
        plt.xticks(rotation=45, ha='right')
        plt.title(
            f'Cell Type Distribution by {condition_column}\n' +
            f'χ²={chi2:.2f}, p={pval:.2e}',
            fontsize=12
        )
        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()

        # Summary statistics
        most_changed = []
        for cell_type in ct_table_norm.columns:
            values = ct_table_norm[cell_type].values
            if len(values) > 1:
                change = values[-1] - values[0]
                most_changed.append((cell_type, change))

        most_changed.sort(key=lambda x: abs(x[1]), reverse=True)
        top_changes = "\n".join([
            f"   {ct}: {ch:+.1f}%"
            for ct, ch in most_changed[:5]
        ])

        color_info = ""
        if plot_type == "heatmap":
            color_info = f"\n🎨 Colormap: {cmap}"
        elif colors:
            color_info = "\n🎨 Colors: custom"
        else:
            color_info = f"\n🎨 Palette: {palette}"

        result_text = f"""📊 Cell Type Proportion Analysis!
🔬 Cell types: {len(ct_table.columns)}
📋 Conditions: {len(ct_table.index)} ({condition_column})
📈 Total cells: {ct_table.sum().sum():,}{color_info}

🧪 Statistical test:
   χ² = {chi2:.2f}
   p-value = {pval:.2e}
   {'✅ Significant' if pval < 0.05 else '❌ Not significant'} (α=0.05)

📉 Top proportion changes:
{top_changes}

💾 Saved: {save_path}"""

        return result_text

    except Exception as e:
        logger.error(f"Cell proportion plot error: {e}", exc_info=True)
        return f"❌ {e}\n{PALETTE_HELP}"


async def sc_plot_violin(arguments: dict) -> str:
    """Violin plot for gene expression distribution with customizable colors"""
    adata_path = arguments.get("adata_path", "/tmp/sc_umap.h5ad")
    genes = arguments.get("genes", [])
    groupby = arguments.get("groupby", "leiden")
    save_path = arguments.get("save_path", "/tmp/violin_plot.png")
    palette = arguments.get("palette")  # 'tab20', 'Set1', 'viridis', list, or dict
    colors = arguments.get("colors")  # Alias for palette (list of colors)
    stripplot = arguments.get("stripplot", True)  # Show individual points
    inner = arguments.get("inner", "box")  # 'box', 'quartile', 'point', 'stick', None

    try:
        import scanpy as sc
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        adata = read_h5ad_compat(adata_path)

        if not genes:
            return f"❌ Please provide gene list in 'genes' parameter\n{PALETTE_HELP}"

        # Validate genes
        valid_genes = [g for g in genes if g in adata.var_names]
        if not valid_genes:
            return f"❌ None of {genes} found in dataset"

        # Handle color settings
        color_param = colors if colors else palette

        # Build plot kwargs
        plot_kwargs = {
            'groupby': groupby,
            'save': False,
            'show': False,
            'rotation': 45,
            'stripplot': stripplot,
            'inner': inner
        }

        if color_param:
            if isinstance(color_param, dict):
                plot_kwargs['palette'] = color_param
            elif isinstance(color_param, list):
                plot_kwargs['palette'] = color_param
            else:
                # String palette name
                plot_kwargs['palette'] = color_param

        # Plot
        sc.pl.violin(adata, valid_genes, **plot_kwargs)
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()

        color_info = ""
        if color_param:
            if isinstance(color_param, str):
                color_info = f"\n🎨 Palette: {color_param}"
            else:
                color_info = "\n🎨 Colors: custom"

        result = f"""🎻 Violin Plot Created!
🧬 Genes: {', '.join(valid_genes)}
📊 Grouped by: {groupby}{color_info}
💾 Saved: {save_path}"""

        return result

    except Exception as e:
        logger.error(f"Violin plot error: {e}", exc_info=True)
        return f"❌ {e}\n{PALETTE_HELP}"


async def sc_plot_dotplot(arguments: dict) -> str:
    """Dot plot for marker gene expression patterns with customizable colors"""
    adata_path = arguments.get("adata_path", "/tmp/sc_umap.h5ad")
    genes = arguments.get("genes", [])
    groupby = arguments.get("groupby", "leiden")
    save_path = arguments.get("save_path", "/tmp/dotplot.png")
    cmap = arguments.get("cmap", "Reds")  # Colormap for expression: 'viridis', 'Blues', 'RdBu', etc.
    dot_max = arguments.get("dot_max")  # Max dot size (fraction, 0-1)
    dot_min = arguments.get("dot_min")  # Min dot size (fraction, 0-1)
    vmin = arguments.get("vmin")  # Min value for color scale
    vmax = arguments.get("vmax")  # Max value for color scale
    standard_scale = arguments.get("standard_scale")  # 'var' or 'group' for normalization

    try:
        import scanpy as sc
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        adata = read_h5ad_compat(adata_path)

        if not genes:
            return f"❌ Please provide gene list in 'genes' parameter\n{PALETTE_HELP}"

        # Validate genes
        valid_genes = [g for g in genes if g in adata.var_names]
        if not valid_genes:
            return f"❌ None of {genes} found in dataset"

        # Build plot kwargs
        plot_kwargs = {
            'groupby': groupby,
            'save': False,
            'show': False,
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

        # Plot
        sc.pl.dotplot(adata, valid_genes, **plot_kwargs)
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()

        result = f"""⚫ Dot Plot Created!
🧬 Genes: {', '.join(valid_genes)}
📊 Grouped by: {groupby}
🎨 Colormap: {cmap}
💾 Saved: {save_path}

💡 Reading:
   - Dot size = % of cells expressing
   - Color = mean expression level"""

        return result

    except Exception as e:
        logger.error(f"Dot plot error: {e}", exc_info=True)
        return f"❌ {e}\n{PALETTE_HELP}"


async def sc_plot_heatmap(arguments: dict) -> str:
    """Heatmap for gene expression matrix with customizable colors"""
    adata_path = arguments.get("adata_path", "/tmp/sc_umap.h5ad")
    genes = arguments.get("genes", [])
    groupby = arguments.get("groupby", "leiden")
    save_path = arguments.get("save_path", "/tmp/heatmap.png")
    cmap = arguments.get("cmap", "viridis")  # Colormap: 'viridis', 'plasma', 'RdBu_r', 'coolwarm', etc.
    vmin = arguments.get("vmin")  # Min value for color scale
    vmax = arguments.get("vmax")  # Max value for color scale
    vcenter = arguments.get("vcenter")  # Center value for diverging colormaps
    standard_scale = arguments.get("standard_scale")  # 'var' or 'group' for normalization
    swap_axes = arguments.get("swap_axes", True)  # Swap rows and columns
    dendrogram = arguments.get("dendrogram", False)  # Show dendrogram

    try:
        import scanpy as sc
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        adata = read_h5ad_compat(adata_path)

        if not genes:
            return f"❌ Please provide gene list in 'genes' parameter\n{PALETTE_HELP}"

        # Validate genes
        valid_genes = [g for g in genes if g in adata.var_names]
        if not valid_genes:
            return f"❌ None of {genes} found in dataset"

        # Build plot kwargs
        plot_kwargs = {
            'groupby': groupby,
            'save': False,
            'show': False,
            'swap_axes': swap_axes,
            'cmap': cmap,
            'dendrogram': dendrogram
        }

        if vmin is not None:
            plot_kwargs['vmin'] = vmin
        if vmax is not None:
            plot_kwargs['vmax'] = vmax
        if vcenter is not None:
            plot_kwargs['vcenter'] = vcenter
        if standard_scale:
            plot_kwargs['standard_scale'] = standard_scale

        # Plot
        sc.pl.heatmap(adata, valid_genes, **plot_kwargs)
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()

        result = f"""🔥 Heatmap Created!
🧬 Genes: {', '.join(valid_genes)}
📊 Grouped by: {groupby}
🎨 Colormap: {cmap}
💾 Saved: {save_path}"""

        return result

    except Exception as e:
        logger.error(f"Heatmap error: {e}", exc_info=True)
        return f"❌ {e}\n{PALETTE_HELP}"
