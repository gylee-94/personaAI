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
SC-Analysis-MCP Server
Universal MCP server for single-cell RNA-seq analysis

35 tools for complete scanpy-based pipeline:
- Status (1): Check existing h5ad files before starting analysis
- Preprocessing (8): Load h5ad, Load 10X single/multi, QC, Normalize, HVG, Subset clusters/cells
- Dimensionality (2): PCA, UMAP
- Integration (2): Harmony batch correction, Batch effect check
- Clustering (2): Leiden, Rename/merge clusters
- DEG Analysis (10): Find markers, Compare groups, One-vs-rest, Pseudobulk DEG, Get results, Export, Heatmap, Dotplot, Volcano, MA plot
- Visualization (5): UMAP plots, Cell proportions, Violin, Dot, Heatmap
- Aging Analysis (5): Gene trajectory, Gene correlation, Expression variance, Aging DEG, Sex dimorphism
"""

import asyncio
import logging
from typing import Any
from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("sc-analysis-mcp")

# Import tool implementations
from .tools.preprocessing import (
    sc_load_h5ad,
    sc_load_10x,
    sc_load_10x_multi,
    sc_quality_control,
    sc_normalize,
    sc_find_hvg,
    sc_subset_clusters,
    sc_subset_cells,
    sc_check_status
)
from .tools.dimensionality import (
    sc_compute_pca,
    sc_compute_umap
)
from .tools.integration import (
    sc_harmony_integrate,
    sc_check_batch_effect
)
from .tools.clustering import (
    sc_leiden_clustering,
    sc_rename_clusters
)
from .tools.deg_analysis import (
    sc_find_markers,
    sc_get_deg_results,
    sc_export_deg,
    sc_plot_deg_heatmap,
    sc_plot_deg_dotplot,
    sc_compare_groups,
    sc_find_markers_vs_rest,
    sc_pseudobulk_deg,
    sc_plot_volcano,
    sc_plot_ma
)
from .tools.visualization import (
    sc_plot_umap,
    sc_plot_cell_proportions,
    sc_plot_violin,
    sc_plot_dotplot,
    sc_plot_heatmap
)
from .tools.aging_analysis import (
    sc_gene_trajectory,
    sc_gene_correlation,
    sc_expression_variance,
    sc_aging_deg,
    sc_sex_dimorphism
)

# Create server instance
server = Server("sc-analysis-mcp")

# Define all tools with their schemas
TOOLS = [
    # ==========================================================================
    # Status (1 tool)
    # ==========================================================================
    {
        "name": "sc_check_status",
        "description": "Check existing processed h5ad files to see pipeline progress. ALWAYS call this FIRST before starting any analysis to avoid re-running completed steps.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "data_dir": {
                    "type": "string",
                    "description": "Directory to check for h5ad files (default: /tmp)",
                    "default": "/tmp"
                }
            }
        },
        "handler": sc_check_status
    },
    # ==========================================================================
    # Preprocessing (8 tools)
    # ==========================================================================
    {
        "name": "sc_load_h5ad",
        "description": "Load h5ad file with validation and summary",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to .h5ad file"
                }
            },
            "required": ["file_path"]
        },
        "handler": sc_load_h5ad
    },
    {
        "name": "sc_load_10x",
        "description": "Load single 10X Genomics sample (matrix.mtx, barcodes.tsv, features.tsv)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "data_dir": {
                    "type": "string",
                    "description": "Directory containing 10X files (matrix.mtx, barcodes.tsv, features.tsv)"
                },
                "gex_only": {
                    "type": "boolean",
                    "description": "Load only gene expression data (ignore antibody capture, etc.)",
                    "default": True
                }
            },
            "required": ["data_dir"]
        },
        "handler": sc_load_10x
    },
    {
        "name": "sc_load_10x_multi",
        "description": "Load multiple 10X samples with automatic batch/condition detection from folder names. Supports CellRanger output and custom directory structures.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "data_dir": {
                    "type": "string",
                    "description": "Parent directory containing sample folders (e.g., Sample1/, Sample2/)"
                },
                "metadata_file": {
                    "type": "string",
                    "description": "Optional CSV/TSV file with sample annotations (columns: sample_id, condition, batch, etc.)"
                },
                "custom_pattern": {
                    "type": "string",
                    "description": "Optional regex pattern for custom folder name parsing"
                },
                "gex_only": {
                    "type": "boolean",
                    "description": "Load only gene expression data",
                    "default": True
                }
            },
            "required": ["data_dir"]
        },
        "handler": sc_load_10x_multi
    },
    {
        "name": "sc_quality_control",
        "description": "QC filtering: remove low-quality cells and genes",
        "inputSchema": {
            "type": "object",
            "properties": {
                "adata_path": {
                    "type": "string",
                    "description": "Path to h5ad file",
                    "default": "/tmp/sc_loaded.h5ad"
                },
                "min_genes": {
                    "type": "integer",
                    "description": "Minimum genes per cell",
                    "default": 200
                },
                "min_cells": {
                    "type": "integer",
                    "description": "Minimum cells per gene",
                    "default": 3
                },
                "max_mt_percent": {
                    "type": "number",
                    "description": "Maximum mitochondrial percentage",
                    "default": 20.0
                }
            }
        },
        "handler": sc_quality_control
    },
    {
        "name": "sc_normalize",
        "description": "Normalize expression data (total count + log1p)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "adata_path": {
                    "type": "string",
                    "default": "/tmp/sc_qc.h5ad"
                },
                "target_sum": {
                    "type": "integer",
                    "default": 10000
                }
            }
        },
        "handler": sc_normalize
    },
    {
        "name": "sc_find_hvg",
        "description": "Find highly variable genes",
        "inputSchema": {
            "type": "object",
            "properties": {
                "adata_path": {
                    "type": "string",
                    "default": "/tmp/sc_norm.h5ad"
                },
                "n_top_genes": {
                    "type": "integer",
                    "default": 2000
                }
            }
        },
        "handler": sc_find_hvg
    },
    {
        "name": "sc_subset_clusters",
        "description": "Subset specific clusters to create a new dataset for focused analysis (e.g., extract only T cells)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "adata_path": {
                    "type": "string",
                    "description": "Path to h5ad file",
                    "default": "/tmp/sc_umap.h5ad"
                },
                "cluster_key": {
                    "type": "string",
                    "description": "Column name containing cluster labels",
                    "default": "leiden"
                },
                "clusters": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of cluster IDs to keep (e.g., ['0', '1', '3'] or ['T_cell', 'B_cell'])"
                },
                "output_path": {
                    "type": "string",
                    "description": "Output path for subset data (optional, auto-generated if not provided)"
                }
            },
            "required": ["clusters"]
        },
        "handler": sc_subset_clusters
    },
    {
        "name": "sc_subset_cells",
        "description": "Subset cells based on metadata conditions using flexible filtering (pandas query syntax or dict)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "adata_path": {
                    "type": "string",
                    "description": "Path to h5ad file",
                    "default": "/tmp/sc_umap.h5ad"
                },
                "condition": {
                    "type": "string",
                    "description": "Query string (pandas syntax): e.g., \"cell_type == 'T_cell' and age == 'Young'\""
                },
                "conditions": {
                    "type": "object",
                    "description": "Dict of conditions: e.g., {\"cell_type\": \"T_cell\", \"age\": [\"Young\", \"Middle\"]}"
                },
                "output_path": {
                    "type": "string",
                    "description": "Output path for subset data (optional)"
                }
            }
        },
        "handler": sc_subset_cells
    },

    # ==========================================================================
    # Dimensionality (2 tools)
    # ==========================================================================
    {
        "name": "sc_compute_pca",
        "description": "Compute PCA for dimensionality reduction",
        "inputSchema": {
            "type": "object",
            "properties": {
                "adata_path": {
                    "type": "string",
                    "default": "/tmp/sc_hvg.h5ad"
                },
                "n_pcs": {
                    "type": "integer",
                    "default": 50
                }
            }
        },
        "handler": sc_compute_pca
    },
    {
        "name": "sc_compute_umap",
        "description": "Compute UMAP embedding with neighbor graph",
        "inputSchema": {
            "type": "object",
            "properties": {
                "adata_path": {
                    "type": "string",
                    "default": "/tmp/sc_pca.h5ad"
                },
                "n_neighbors": {
                    "type": "integer",
                    "default": 15
                },
                "n_pcs": {
                    "type": "integer",
                    "default": 40
                },
                "use_rep": {
                    "type": "string",
                    "default": "X_pca",
                    "description": "Representation to use (e.g., 'X_pca' or 'X_pca_harmony')"
                }
            }
        },
        "handler": sc_compute_umap
    },

    # ==========================================================================
    # Integration (2 tools)
    # ==========================================================================
    {
        "name": "sc_harmony_integrate",
        "description": "Harmony batch correction - removes batch effects while preserving biological variation",
        "inputSchema": {
            "type": "object",
            "properties": {
                "adata_path": {
                    "type": "string",
                    "default": "/tmp/sc_pca.h5ad",
                    "description": "Path to h5ad file (after PCA)"
                },
                "batch_key": {
                    "type": "string",
                    "description": "Column name in adata.obs containing batch labels"
                },
                "theta": {
                    "type": "number",
                    "default": 2.0,
                    "description": "Diversity clustering penalty (0-4). Higher = more aggressive correction"
                },
                "sigma": {
                    "type": "number",
                    "default": 0.1,
                    "description": "Width of soft kmeans clusters"
                },
                "max_iter_harmony": {
                    "type": "integer",
                    "default": 10,
                    "description": "Maximum iterations"
                },
                "use_rep": {
                    "type": "string",
                    "default": "X_pca",
                    "description": "Representation to use for correction"
                },
                "basis": {
                    "type": "string",
                    "default": "X_pca_harmony",
                    "description": "Output basis name for corrected embeddings"
                }
            },
            "required": ["batch_key"]
        },
        "handler": sc_harmony_integrate
    },
    {
        "name": "sc_check_batch_effect",
        "description": "Quick diagnostic to visualize batch effects in PCA space",
        "inputSchema": {
            "type": "object",
            "properties": {
                "adata_path": {
                    "type": "string",
                    "default": "/tmp/sc_pca.h5ad"
                },
                "batch_key": {
                    "type": "string",
                    "description": "Column name with batch labels"
                },
                "use_rep": {
                    "type": "string",
                    "default": "X_pca",
                    "description": "Representation to check"
                },
                "save_path": {
                    "type": "string",
                    "default": "/tmp/batch_effect_check.png"
                }
            },
            "required": ["batch_key"]
        },
        "handler": sc_check_batch_effect
    },

    # ==========================================================================
    # Clustering (2 tools)
    # ==========================================================================
    {
        "name": "sc_leiden_clustering",
        "description": "Leiden/Louvain clustering algorithm",
        "inputSchema": {
            "type": "object",
            "properties": {
                "adata_path": {
                    "type": "string",
                    "default": "/tmp/sc_umap.h5ad"
                },
                "resolution": {
                    "type": "number",
                    "default": 0.5
                }
            }
        },
        "handler": sc_leiden_clustering
    },
    {
        "name": "sc_rename_clusters",
        "description": "Rename or merge cluster labels with a user-defined mapping. Supports: renaming numbers to cell type names, merging multiple clusters into one, partial remapping (unmapped labels are kept as-is). Optionally saves to a new column to preserve the original.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "adata_path": {
                    "type": "string",
                    "default": "/tmp/sc_umap.h5ad",
                    "description": "Path to h5ad file"
                },
                "cluster_key": {
                    "type": "string",
                    "default": "leiden",
                    "description": "Column name to apply mapping to (e.g. 'leiden')"
                },
                "mapping": {
                    "type": "object",
                    "description": "Label mapping dict. e.g. {\"2\": \"NK cell\", \"4\": \"NK cell\", \"0\": \"T cell\"}. Unmapped labels are kept as-is."
                },
                "new_key": {
                    "type": "string",
                    "description": "If provided, save renamed labels to a new column (e.g. 'cell_type_manual') instead of overwriting cluster_key. Recommended to preserve original clustering."
                },
                "output_path": {
                    "type": "string",
                    "description": "Output h5ad path. Defaults to overwriting adata_path."
                }
            },
            "required": ["mapping"]
        },
        "handler": sc_rename_clusters
    },

    # ==========================================================================
    # Visualization (5 tools)
    # ==========================================================================
    {
        "name": "sc_plot_umap",
        "description": "Plot UMAP colored by metadata or gene expression with customizable colors",
        "inputSchema": {
            "type": "object",
            "properties": {
                "adata_path": {
                    "type": "string",
                    "default": "/tmp/sc_umap.h5ad"
                },
                "color": {
                    "type": "string",
                    "default": "leiden",
                    "description": "Column name or gene name to color by"
                },
                "palette": {
                    "type": ["string", "array", "object"],
                    "description": "For categorical: 'tab20', 'Set1', list of hex colors, or dict mapping categories to colors"
                },
                "cmap": {
                    "type": "string",
                    "description": "For continuous (gene expression): 'viridis', 'plasma', 'RdBu', 'coolwarm', etc."
                },
                "vmin": {
                    "type": "number",
                    "description": "Minimum value for continuous colormap"
                },
                "vmax": {
                    "type": "number",
                    "description": "Maximum value for continuous colormap"
                },
                "vcenter": {
                    "type": "number",
                    "description": "Center value for diverging colormaps"
                },
                "save_path": {
                    "type": "string",
                    "description": "Output path (optional)"
                }
            }
        },
        "handler": sc_plot_umap
    },
    {
        "name": "sc_plot_cell_proportions",
        "description": "Analyze cell type proportions across conditions with Chi-square test",
        "inputSchema": {
            "type": "object",
            "properties": {
                "adata_path": {
                    "type": "string",
                    "default": "/tmp/sc_umap.h5ad"
                },
                "cell_type_column": {
                    "type": "string",
                    "description": "Column containing cell type annotations"
                },
                "condition_column": {
                    "type": "string",
                    "description": "Column containing condition/group information"
                },
                "plot_type": {
                    "type": "string",
                    "enum": ["stacked_bar", "heatmap", "line"],
                    "default": "stacked_bar"
                },
                "normalize": {
                    "type": "boolean",
                    "default": True
                },
                "palette": {
                    "type": "string",
                    "default": "tab20",
                    "description": "For stacked_bar/line: 'tab20', 'Set1', 'viridis', etc."
                },
                "cmap": {
                    "type": "string",
                    "default": "YlOrRd",
                    "description": "For heatmap: 'viridis', 'RdBu', 'coolwarm', etc."
                },
                "colors": {
                    "type": ["array", "object"],
                    "description": "Custom colors: list of hex colors or dict mapping cell types to colors"
                },
                "save_path": {
                    "type": "string",
                    "default": "/tmp/cell_proportions.png"
                }
            },
            "required": ["cell_type_column", "condition_column"]
        },
        "handler": sc_plot_cell_proportions
    },
    {
        "name": "sc_plot_violin",
        "description": "Violin plot for gene expression distribution with customizable colors",
        "inputSchema": {
            "type": "object",
            "properties": {
                "adata_path": {
                    "type": "string",
                    "default": "/tmp/sc_umap.h5ad"
                },
                "genes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of gene names to plot"
                },
                "groupby": {
                    "type": "string",
                    "default": "leiden",
                    "description": "Column to group cells by"
                },
                "palette": {
                    "type": ["string", "array", "object"],
                    "description": "Color palette: 'tab20', 'Set1', list of colors, or dict"
                },
                "colors": {
                    "type": ["array", "object"],
                    "description": "Alias for palette: list of hex colors or dict"
                },
                "stripplot": {
                    "type": "boolean",
                    "default": True,
                    "description": "Show individual data points"
                },
                "inner": {
                    "type": "string",
                    "enum": ["box", "quartile", "point", "stick"],
                    "default": "box",
                    "description": "Inner plot type"
                },
                "save_path": {
                    "type": "string",
                    "default": "/tmp/violin_plot.png"
                }
            },
            "required": ["genes"]
        },
        "handler": sc_plot_violin
    },
    {
        "name": "sc_plot_dotplot",
        "description": "Dot plot for marker gene expression patterns with customizable colors",
        "inputSchema": {
            "type": "object",
            "properties": {
                "adata_path": {
                    "type": "string",
                    "default": "/tmp/sc_umap.h5ad"
                },
                "genes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of gene names to plot"
                },
                "groupby": {
                    "type": "string",
                    "default": "leiden",
                    "description": "Column to group cells by"
                },
                "cmap": {
                    "type": "string",
                    "default": "Reds",
                    "description": "Colormap for expression: 'viridis', 'Blues', 'YlOrRd', etc."
                },
                "dot_max": {
                    "type": "number",
                    "description": "Maximum dot size (fraction, 0-1)"
                },
                "dot_min": {
                    "type": "number",
                    "description": "Minimum dot size (fraction, 0-1)"
                },
                "vmin": {
                    "type": "number",
                    "description": "Minimum value for color scale"
                },
                "vmax": {
                    "type": "number",
                    "description": "Maximum value for color scale"
                },
                "standard_scale": {
                    "type": "string",
                    "enum": ["var", "group"],
                    "description": "Standardize values by 'var' (genes) or 'group'"
                },
                "save_path": {
                    "type": "string",
                    "default": "/tmp/dotplot.png"
                }
            },
            "required": ["genes"]
        },
        "handler": sc_plot_dotplot
    },
    {
        "name": "sc_plot_heatmap",
        "description": "Heatmap for gene expression matrix with customizable colors",
        "inputSchema": {
            "type": "object",
            "properties": {
                "adata_path": {
                    "type": "string",
                    "default": "/tmp/sc_umap.h5ad"
                },
                "genes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of gene names to plot"
                },
                "groupby": {
                    "type": "string",
                    "default": "leiden",
                    "description": "Column to group cells by"
                },
                "cmap": {
                    "type": "string",
                    "default": "viridis",
                    "description": "Colormap: 'viridis', 'plasma', 'RdBu_r', 'coolwarm', etc."
                },
                "vmin": {
                    "type": "number",
                    "description": "Minimum value for color scale"
                },
                "vmax": {
                    "type": "number",
                    "description": "Maximum value for color scale"
                },
                "vcenter": {
                    "type": "number",
                    "description": "Center value for diverging colormaps"
                },
                "standard_scale": {
                    "type": "string",
                    "enum": ["var", "group"],
                    "description": "Standardize values by 'var' (genes) or 'group'"
                },
                "swap_axes": {
                    "type": "boolean",
                    "default": True,
                    "description": "Swap rows and columns"
                },
                "dendrogram": {
                    "type": "boolean",
                    "default": False,
                    "description": "Show dendrogram"
                },
                "save_path": {
                    "type": "string",
                    "default": "/tmp/heatmap.png"
                }
            },
            "required": ["genes"]
        },
        "handler": sc_plot_heatmap
    },

    # ==========================================================================
    # DEG Analysis (10 tools)
    # ==========================================================================
    {
        "name": "sc_find_markers",
        "description": "Find marker genes for each cluster using differential expression analysis",
        "inputSchema": {
            "type": "object",
            "properties": {
                "adata_path": {
                    "type": "string",
                    "default": "/tmp/sc_umap.h5ad",
                    "description": "Path to h5ad file (after clustering)"
                },
                "groupby": {
                    "type": "string",
                    "default": "leiden",
                    "description": "Column name to group by"
                },
                "method": {
                    "type": "string",
                    "enum": ["t-test", "wilcoxon", "logreg"],
                    "default": "wilcoxon",
                    "description": "Statistical test method"
                },
                "n_genes": {
                    "type": "integer",
                    "default": 100,
                    "description": "Number of top genes per group"
                },
                "use_raw": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to use raw counts"
                },
                "corr_method": {
                    "type": "string",
                    "enum": ["bonferroni", "fdr_bh"],
                    "default": "fdr_bh",
                    "description": "Multiple testing correction method"
                },
                "key_added": {
                    "type": "string",
                    "default": "rank_genes_groups",
                    "description": "Key to store results in adata.uns"
                }
            }
        },
        "handler": sc_find_markers
    },
    {
        "name": "sc_get_deg_results",
        "description": "Get DEG results table with filtering options",
        "inputSchema": {
            "type": "object",
            "properties": {
                "adata_path": {
                    "type": "string",
                    "default": "/tmp/sc_umap_deg.h5ad",
                    "description": "Path to h5ad file with DEG results"
                },
                "key": {
                    "type": "string",
                    "default": "rank_genes_groups",
                    "description": "Key in adata.uns containing results"
                },
                "group": {
                    "type": "string",
                    "description": "Specific group to show (optional)"
                },
                "n_genes": {
                    "type": "integer",
                    "default": 10,
                    "description": "Number of top genes to show per group"
                },
                "pval_cutoff": {
                    "type": "number",
                    "default": 0.05,
                    "description": "P-value cutoff for filtering"
                },
                "logfc_cutoff": {
                    "type": "number",
                    "default": 0.5,
                    "description": "Log fold-change cutoff"
                }
            }
        },
        "handler": sc_get_deg_results
    },
    {
        "name": "sc_export_deg",
        "description": "Export DEG results to CSV or Excel files",
        "inputSchema": {
            "type": "object",
            "properties": {
                "adata_path": {
                    "type": "string",
                    "default": "/tmp/sc_umap_deg.h5ad"
                },
                "key": {
                    "type": "string",
                    "default": "rank_genes_groups"
                },
                "output_dir": {
                    "type": "string",
                    "default": "/tmp/deg_results",
                    "description": "Directory to save results"
                },
                "format": {
                    "type": "string",
                    "enum": ["csv", "excel", "both"],
                    "default": "both",
                    "description": "Export format"
                },
                "pval_cutoff": {
                    "type": "number",
                    "default": 0.05
                },
                "logfc_cutoff": {
                    "type": "number",
                    "default": 0.5
                }
            }
        },
        "handler": sc_export_deg
    },
    {
        "name": "sc_plot_deg_heatmap",
        "description": "Create heatmap visualization of top DEGs with customizable colors",
        "inputSchema": {
            "type": "object",
            "properties": {
                "adata_path": {
                    "type": "string",
                    "default": "/tmp/sc_umap_deg.h5ad"
                },
                "key": {
                    "type": "string",
                    "default": "rank_genes_groups"
                },
                "n_genes": {
                    "type": "integer",
                    "default": 10,
                    "description": "Number of top genes per group to show"
                },
                "groupby": {
                    "type": "string",
                    "default": "leiden",
                    "description": "Column to group cells by"
                },
                "cmap": {
                    "type": "string",
                    "default": "viridis",
                    "description": "Colormap: 'viridis', 'plasma', 'RdBu_r', 'coolwarm', etc."
                },
                "vmin": {
                    "type": "number",
                    "description": "Minimum value for color scale"
                },
                "vmax": {
                    "type": "number",
                    "description": "Maximum value for color scale"
                },
                "standard_scale": {
                    "type": "string",
                    "enum": ["var", "group"],
                    "description": "Standardize values by 'var' (genes) or 'group'"
                },
                "save_path": {
                    "type": "string",
                    "default": "/tmp/deg_heatmap.png"
                },
                "figsize": {
                    "type": "array",
                    "items": {"type": "number"},
                    "default": [12, 10],
                    "description": "Figure size as [width, height]"
                },
                "show_gene_labels": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to show gene names"
                }
            }
        },
        "handler": sc_plot_deg_heatmap
    },
    {
        "name": "sc_plot_deg_dotplot",
        "description": "Create dotplot visualization of top DEGs with customizable colors",
        "inputSchema": {
            "type": "object",
            "properties": {
                "adata_path": {
                    "type": "string",
                    "default": "/tmp/sc_umap_deg.h5ad"
                },
                "key": {
                    "type": "string",
                    "default": "rank_genes_groups"
                },
                "n_genes": {
                    "type": "integer",
                    "default": 5,
                    "description": "Number of top genes per group to show"
                },
                "groupby": {
                    "type": "string",
                    "default": "leiden",
                    "description": "Column to group cells by"
                },
                "cmap": {
                    "type": "string",
                    "default": "Reds",
                    "description": "Colormap: 'viridis', 'Blues', 'YlOrRd', etc."
                },
                "dot_max": {
                    "type": "number",
                    "description": "Maximum dot size (fraction, 0-1)"
                },
                "dot_min": {
                    "type": "number",
                    "description": "Minimum dot size (fraction, 0-1)"
                },
                "vmin": {
                    "type": "number",
                    "description": "Minimum value for color scale"
                },
                "vmax": {
                    "type": "number",
                    "description": "Maximum value for color scale"
                },
                "standard_scale": {
                    "type": "string",
                    "enum": ["var", "group"],
                    "description": "Standardize values by 'var' (genes) or 'group'"
                },
                "save_path": {
                    "type": "string",
                    "default": "/tmp/deg_dotplot.png"
                },
                "figsize": {
                    "type": "array",
                    "items": {"type": "number"},
                    "default": [12, 8],
                    "description": "Figure size as [width, height]"
                }
            }
        },
        "handler": sc_plot_deg_dotplot
    },
    {
        "name": "sc_compare_groups",
        "description": "Compare two specific groups to find differentially expressed genes (e.g., Young vs Aged, Control vs Treatment)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "adata_path": {
                    "type": "string",
                    "default": "/tmp/sc_umap.h5ad"
                },
                "groupby": {
                    "type": "string",
                    "description": "Column name containing groups (required)"
                },
                "group1": {
                    "type": "string",
                    "description": "First group name (e.g., 'Young', 'Control') (required)"
                },
                "group2": {
                    "type": "string",
                    "description": "Second group name (e.g., 'Aged', 'Treatment') (required)"
                },
                "method": {
                    "type": "string",
                    "enum": ["t-test", "wilcoxon", "logreg"],
                    "default": "wilcoxon"
                },
                "n_genes": {
                    "type": "integer",
                    "default": 100
                },
                "use_raw": {
                    "type": "boolean",
                    "default": True
                },
                "corr_method": {
                    "type": "string",
                    "enum": ["bonferroni", "fdr_bh"],
                    "default": "fdr_bh"
                },
                "key_added": {
                    "type": "string",
                    "description": "Key to store results (auto-generated if not provided)"
                }
            },
            "required": ["groupby", "group1", "group2"]
        },
        "handler": sc_compare_groups
    },
    {
        "name": "sc_find_markers_vs_rest",
        "description": "Find marker genes for specific groups vs all other cells (one-vs-rest analysis)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "adata_path": {
                    "type": "string",
                    "default": "/tmp/sc_umap.h5ad"
                },
                "groupby": {
                    "type": "string",
                    "default": "leiden",
                    "description": "Column name to group by"
                },
                "groups": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of specific groups to analyze (optional, analyzes all if not specified)"
                },
                "reference": {
                    "type": "string",
                    "default": "rest",
                    "description": "Reference group name or 'rest'"
                },
                "method": {
                    "type": "string",
                    "enum": ["t-test", "wilcoxon", "logreg"],
                    "default": "wilcoxon"
                },
                "n_genes": {
                    "type": "integer",
                    "default": 100
                },
                "use_raw": {
                    "type": "boolean",
                    "default": True
                },
                "corr_method": {
                    "type": "string",
                    "enum": ["bonferroni", "fdr_bh"],
                    "default": "fdr_bh"
                },
                "key_added": {
                    "type": "string",
                    "default": "rank_genes_groups_vs_rest"
                }
            }
        },
        "handler": sc_find_markers_vs_rest
    },
    {
        "name": "sc_pseudobulk_deg",
        "description": "Pseudobulk differential expression analysis using DESeq2. Aggregates single-cell counts by sample for robust statistical analysis.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "adata_path": {
                    "type": "string",
                    "default": "/tmp/sc_umap.h5ad",
                    "description": "Path to h5ad file"
                },
                "sample_key": {
                    "type": "string",
                    "description": "Column containing sample/replicate IDs (required)"
                },
                "condition_key": {
                    "type": "string",
                    "description": "Column containing condition labels (required)"
                },
                "condition1": {
                    "type": "string",
                    "description": "First condition to compare (e.g., 'Control' or 'Young')"
                },
                "condition2": {
                    "type": "string",
                    "description": "Second condition to compare (e.g., 'Treatment' or 'Aged')"
                },
                "cell_type_key": {
                    "type": "string",
                    "description": "Optional: Column for cell type to analyze specific populations"
                },
                "cell_type": {
                    "type": "string",
                    "description": "Optional: Specific cell type to analyze"
                },
                "min_cells": {
                    "type": "integer",
                    "default": 10,
                    "description": "Minimum cells per sample to include"
                },
                "min_counts": {
                    "type": "integer",
                    "default": 10,
                    "description": "Minimum total counts per gene"
                },
                "output_dir": {
                    "type": "string",
                    "default": "/tmp/pseudobulk_results",
                    "description": "Directory to save pseudobulk DEG results"
                }
            },
            "required": ["sample_key", "condition_key", "condition1", "condition2"]
        },
        "handler": sc_pseudobulk_deg
    },
    {
        "name": "sc_plot_volcano",
        "description": "Create volcano plot for DEG visualization with customizable colors",
        "inputSchema": {
            "type": "object",
            "properties": {
                "adata_path": {
                    "type": "string",
                    "default": "/tmp/sc_umap_deg.h5ad",
                    "description": "Path to h5ad file with DEG results"
                },
                "deg_results": {
                    "type": "string",
                    "description": "Alternative: path to DEG results CSV file"
                },
                "key": {
                    "type": "string",
                    "default": "pseudobulk_deg",
                    "description": "Key in adata.uns containing DEG results"
                },
                "group": {
                    "type": "string",
                    "description": "Specific group to plot (for rank_genes_groups results)"
                },
                "pval_cutoff": {
                    "type": "number",
                    "default": 0.05,
                    "description": "P-value threshold for significance"
                },
                "logfc_cutoff": {
                    "type": "number",
                    "default": 1.0,
                    "description": "Log2 fold change threshold"
                },
                "top_genes": {
                    "type": "integer",
                    "default": 10,
                    "description": "Number of top genes to label"
                },
                "up_color": {
                    "type": "string",
                    "default": "#e74c3c",
                    "description": "Color for upregulated genes (hex or named color)"
                },
                "down_color": {
                    "type": "string",
                    "default": "#3498db",
                    "description": "Color for downregulated genes"
                },
                "ns_color": {
                    "type": "string",
                    "default": "#95a5a6",
                    "description": "Color for non-significant genes"
                },
                "point_size": {
                    "type": "number",
                    "default": 20,
                    "description": "Size of scatter points"
                },
                "alpha": {
                    "type": "number",
                    "default": 0.6,
                    "description": "Transparency of points (0-1)"
                },
                "figsize": {
                    "type": "array",
                    "items": {"type": "number"},
                    "default": [10, 8],
                    "description": "Figure size as [width, height]"
                },
                "save_path": {
                    "type": "string",
                    "default": "/tmp/volcano_plot.png",
                    "description": "Output file path"
                }
            }
        },
        "handler": sc_plot_volcano
    },
    {
        "name": "sc_plot_ma",
        "description": "Create MA plot for DEG visualization with customizable colors",
        "inputSchema": {
            "type": "object",
            "properties": {
                "adata_path": {
                    "type": "string",
                    "default": "/tmp/sc_umap_deg.h5ad",
                    "description": "Path to h5ad file with DEG results"
                },
                "deg_results": {
                    "type": "string",
                    "description": "Alternative: path to DEG results CSV file"
                },
                "key": {
                    "type": "string",
                    "default": "pseudobulk_deg",
                    "description": "Key in adata.uns containing DEG results"
                },
                "group": {
                    "type": "string",
                    "description": "Specific group to plot (for rank_genes_groups results)"
                },
                "pval_cutoff": {
                    "type": "number",
                    "default": 0.05,
                    "description": "P-value threshold for significance"
                },
                "logfc_cutoff": {
                    "type": "number",
                    "default": 1.0,
                    "description": "Log2 fold change threshold"
                },
                "top_genes": {
                    "type": "integer",
                    "default": 10,
                    "description": "Number of top genes to label"
                },
                "up_color": {
                    "type": "string",
                    "default": "#e74c3c",
                    "description": "Color for upregulated genes (hex or named color)"
                },
                "down_color": {
                    "type": "string",
                    "default": "#3498db",
                    "description": "Color for downregulated genes"
                },
                "ns_color": {
                    "type": "string",
                    "default": "#95a5a6",
                    "description": "Color for non-significant genes"
                },
                "point_size": {
                    "type": "number",
                    "default": 20,
                    "description": "Size of scatter points"
                },
                "alpha": {
                    "type": "number",
                    "default": 0.6,
                    "description": "Transparency of points (0-1)"
                },
                "figsize": {
                    "type": "array",
                    "items": {"type": "number"},
                    "default": [10, 8],
                    "description": "Figure size as [width, height]"
                },
                "save_path": {
                    "type": "string",
                    "default": "/tmp/ma_plot.png",
                    "description": "Output file path"
                }
            }
        },
        "handler": sc_plot_ma
    },

    # ==========================================================================
    # Aging Analysis (5 tools)
    # ==========================================================================
    {
        "name": "sc_gene_trajectory",
        "description": "Compute gene expression trajectory across age groups (03m→23m), split by sex. Returns mean±SEM per group with Spearman trend test. Essential for validating age-dependent expression changes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "adata_path": {
                    "type": "string",
                    "description": "Path to h5ad file"
                },
                "genes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of gene symbols (e.g. ['Cyp2e1', 'Srd5a1'])"
                },
                "cell_type": {
                    "type": "string",
                    "description": "Filter to specific Main_cell_type (e.g. 'Hepatocytes')"
                },
                "genotype": {
                    "type": "string",
                    "default": "WT",
                    "description": "Genotype filter (default: WT)"
                },
                "save_path": {
                    "type": "string",
                    "default": "/tmp/aging_gene_trajectory.png"
                }
            },
            "required": ["adata_path", "genes"]
        },
        "handler": sc_gene_trajectory
    },
    {
        "name": "sc_gene_correlation",
        "description": "Compute gene-gene Spearman correlations stratified by sex and/or age. Tests whether gene pairs are co-regulated differently between sexes during aging.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "adata_path": {
                    "type": "string",
                    "description": "Path to h5ad file"
                },
                "gene_pairs": {
                    "type": "array",
                    "items": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 2,
                        "maxItems": 2
                    },
                    "description": "List of gene pairs (e.g. [['Cyp2e1','Srd5a1'], ['Col1a1','Tgfb1']])"
                },
                "stratify_by": {
                    "type": "string",
                    "enum": ["Sex", "Age_group", "All"],
                    "default": "Sex",
                    "description": "Stratification variable"
                },
                "cell_type": {
                    "type": "string",
                    "description": "Filter to specific Main_cell_type"
                },
                "genotype": {
                    "type": "string",
                    "default": "WT"
                },
                "save_path": {
                    "type": "string",
                    "default": "/tmp/aging_gene_correlation.png"
                }
            },
            "required": ["adata_path", "gene_pairs"]
        },
        "handler": sc_gene_correlation
    },
    {
        "name": "sc_expression_variance",
        "description": "Analyze transcriptional noise (CV or Fano factor) changes with aging per sex. Increasing variance = loss of transcriptional control. Key metric for aging biology.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "adata_path": {
                    "type": "string",
                    "description": "Path to h5ad file"
                },
                "genes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of gene symbols to analyze"
                },
                "metric": {
                    "type": "string",
                    "enum": ["cv", "fano"],
                    "default": "cv",
                    "description": "Variance metric: cv (coefficient of variation) or fano (Fano factor)"
                },
                "cell_type": {
                    "type": "string",
                    "description": "Filter to specific Main_cell_type"
                },
                "genotype": {
                    "type": "string",
                    "default": "WT"
                },
                "save_path": {
                    "type": "string",
                    "default": "/tmp/aging_expression_variance.png"
                }
            },
            "required": ["adata_path", "genes"]
        },
        "handler": sc_expression_variance
    },
    {
        "name": "sc_aging_deg",
        "description": "Age-stratified DEG analysis: Young vs Old, split by sex. Uses Wilcoxon rank-sum test. Outputs volcano plots and top DEGs per sex. Identifies sex-specific aging genes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "adata_path": {
                    "type": "string",
                    "description": "Path to h5ad file"
                },
                "young_groups": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": ["03_months"],
                    "description": "Age groups to define 'Young' (e.g. ['03_months'])"
                },
                "old_groups": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": ["23_months"],
                    "description": "Age groups to define 'Old' (e.g. ['23_months'])"
                },
                "cell_type": {
                    "type": "string",
                    "description": "Filter to specific Main_cell_type"
                },
                "genotype": {
                    "type": "string",
                    "default": "WT"
                },
                "n_top": {
                    "type": "integer",
                    "default": 20,
                    "description": "Number of top DEGs to report"
                },
                "save_path": {
                    "type": "string",
                    "default": "/tmp/aging_deg_results.png"
                }
            },
            "required": ["adata_path"]
        },
        "handler": sc_aging_deg
    },
    {
        "name": "sc_sex_dimorphism",
        "description": "Identify sex-dimorphic genes at each age point. Computes Male vs Female log2FC per age group. Detects REVERSAL (direction change), DIVERGING (increasing difference), CONVERGING (decreasing difference) patterns.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "adata_path": {
                    "type": "string",
                    "description": "Path to h5ad file"
                },
                "genes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific genes to analyze. If empty, auto-discovers top sex-dimorphic genes."
                },
                "cell_type": {
                    "type": "string",
                    "description": "Filter to specific Main_cell_type"
                },
                "genotype": {
                    "type": "string",
                    "default": "WT"
                },
                "save_path": {
                    "type": "string",
                    "default": "/tmp/aging_sex_dimorphism.png"
                }
            },
            "required": ["adata_path"]
        },
        "handler": sc_sex_dimorphism
    }
]

# Register tools with MCP server
@server.list_tools()
async def list_tools() -> list[types.Tool]:
    """List all available single-cell analysis tools"""
    return [
        types.Tool(
            name=tool["name"],
            description=tool["description"],
            inputSchema=tool["inputSchema"]
        )
        for tool in TOOLS
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    """Handle tool execution"""
    # Find tool handler
    tool = next((t for t in TOOLS if t["name"] == name), None)
    if not tool:
        raise ValueError(f"Unknown tool: {name}")
    
    try:
        # Execute handler
        result = await tool["handler"](arguments)
        return [types.TextContent(type="text", text=result)]
    except Exception as e:
        logger.error(f"Tool execution error for {name}: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"❌ Error: {str(e)}")]

async def _async_main():
    """Async server entry point"""
    logger.info("🧬 Starting SC-Analysis-MCP Server...")
    logger.info(f"📊 Loaded {len(TOOLS)} single-cell analysis tools")

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )

def main():
    """Main server entry point (sync wrapper for pyproject.toml scripts)"""
    asyncio.run(_async_main())

if __name__ == "__main__":
    main()
