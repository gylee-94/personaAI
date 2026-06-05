# SC-Analysis-MCP

Universal MCP server for single-cell RNA-seq analysis using Scanpy.

## Features

### 35 Tools

**Preprocessing (8 tools)**
- `sc_load_h5ad` - Load and validate h5ad files
- `sc_load_10x` - Load single 10X Genomics sample (matrix.mtx, barcodes.tsv, features.tsv) ⭐NEW
- `sc_load_10x_multi` - Load multiple 10X samples with auto batch/condition detection ⭐NEW
- `sc_quality_control` - Filter low-quality cells and genes
- `sc_normalize` - Normalize expression (total count + log1p)
- `sc_find_hvg` - Select highly variable genes
- `sc_subset_clusters` - Extract specific clusters for focused analysis ⭐NEW
- `sc_subset_cells` - Filter cells by metadata conditions ⭐NEW

**Dimensionality Reduction (2 tools)**
- `sc_compute_pca` - Principal component analysis
- `sc_compute_umap` - UMAP embedding with KNN graph

**Integration (2 tools)**
- `sc_harmony_integrate` - Harmony batch correction
- `sc_check_batch_effect` - Visualize batch effects

**Clustering (2 tools)**
- `sc_leiden_clustering` - Leiden/Louvain clustering
- `sc_rename_clusters` - Rename or merge cluster labels

**DEG Analysis (10 tools)**
- `sc_find_markers` - Find marker genes for each group (any metadata column)
- `sc_compare_groups` - Compare two specific groups (e.g., Young vs Aged)
- `sc_find_markers_vs_rest` - One-vs-rest analysis for specific groups
- `sc_pseudobulk_deg` - Pseudobulk DEG analysis using DESeq2 (robust for replicates) ⭐NEW
- `sc_get_deg_results` - View DEG results with filtering
- `sc_export_deg` - Export results to CSV/Excel
- `sc_plot_deg_heatmap` - Heatmap of top DEGs
- `sc_plot_deg_dotplot` - Dotplot of top DEGs
- `sc_plot_volcano` - Volcano plot (-log10 p-value vs log2 fold change) ⭐NEW
- `sc_plot_ma` - MA plot (log2 fold change vs mean expression) ⭐NEW

**Visualization (5 tools)**
- `sc_plot_umap` - UMAP plots colored by metadata/genes
- `sc_plot_cell_proportions` - Cell type distribution with Chi-square test
- `sc_plot_violin` - Violin plots for gene expression
- `sc_plot_dotplot` - Dot plots for marker genes
- `sc_plot_heatmap` - Expression heatmaps

## Installation

### Step 1: Install Dependencies

```bash
# Navigate to project directory
cd /path/to/sc_analysis_mcp

# Create virtual environment (recommended)
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate  # macOS/Linux
# OR
.venv\Scripts\activate     # Windows

# Install package in editable mode
pip install -e .
```

### Step 2: Configure Claude Desktop

Add to your `claude_desktop_config.json`:

**Method 1: Using virtual environment (Recommended)**
```json
{
  "mcpServers": {
    "sc_analysis_mcp": {
      "command": "/path/to/sc_analysis_mcp/.venv/bin/python",
      "args": [
        "-m",
        "sc_analysis_mcp.server"
      ]
    }
  }
}
```

**Method 2: Using system Python**
```json
{
  "mcpServers": {
    "sc_analysis_mcp": {
      "command": "python3",
      "args": [
        "-m",
        "sc_analysis_mcp.server"
      ],
      "env": {
        "PYTHONPATH": "/path/to/sc_analysis_mcp"
      }
    }
  }
}
```

Replace `/path/to/sc_analysis_mcp` with your actual installation path.

### Step 3: Restart Claude Desktop

After configuration, restart Claude Desktop to load the MCP server.

## Quick Start

### Load 10X Multi-Sample Data (NEW)
```python
# Load multiple 10X samples with automatic detection
sc_load_10x_multi(data_dir="/path/to/samples/")

# Directory structure auto-detected:
# samples/
# ├── Sample1_Control_Rep1/  → condition=Control, replicate=1
# ├── Sample1_Control_Rep2/  → condition=Control, replicate=2
# ├── Sample2_Treatment_Rep1/ → condition=Treatment, replicate=1
# └── Sample2_Treatment_Rep2/ → condition=Treatment, replicate=2

# With custom metadata file:
sc_load_10x_multi(
    data_dir="/path/to/samples/",
    metadata_file="/path/to/sample_metadata.csv"
)
```

### Standard Pipeline
```python
# 1. Load data
sc_load_h5ad(file_path="/path/to/data.h5ad")

# 2. Quality control
sc_quality_control(min_genes=200, max_mt_percent=20)

# 3. Normalize
sc_normalize(target_sum=10000)

# 4. Find HVGs
sc_find_hvg(n_top_genes=2000)

# 5. PCA
sc_compute_pca(n_pcs=50)

# 6. UMAP
sc_compute_umap(n_neighbors=15)

# 7. Clustering
sc_leiden_clustering(resolution=0.5)

# 8. Find marker genes
sc_find_markers(groupby="leiden", method="wilcoxon", n_genes=100)

# 9. View top DEGs
sc_get_deg_results(n_genes=10, pval_cutoff=0.05)

# 10. Export DEG results
sc_export_deg(output_dir="/tmp/deg_results", format="both")

# 11. Visualize DEGs
sc_plot_deg_heatmap(n_genes=10)
sc_plot_deg_dotplot(n_genes=5)

# 12. UMAP visualization
sc_plot_umap(color="leiden")
```

### With Batch Correction (Harmony)
```python
# ... Steps 1-5 same as above ...

# 6. Check batch effects
sc_check_batch_effect(batch_key="batch")

# 7. Harmony integration (if needed)
sc_harmony_integrate(batch_key="batch", theta=2.0)

# 8. UMAP on corrected data
sc_compute_umap(use_rep="X_pca_harmony")

# 9. Clustering
sc_leiden_clustering()

# 10. Find marker genes
sc_find_markers(groupby="leiden")

# 11. Compare before/after
sc_plot_umap(color="batch")

# 12. Visualize DEGs
sc_plot_deg_heatmap(n_genes=10)
```

### Advanced DEG Analysis Examples

#### Compare Two Conditions (e.g., Young vs Aged)
```python
# Compare specific groups
sc_compare_groups(
    groupby="age_group",
    group1="Young",
    group2="Aged",
    method="wilcoxon",
    n_genes=200
)

# Export condition-specific results
sc_export_deg(
    key="deg_Young_vs_Aged",
    output_dir="/results/age_comparison"
)
```

#### Find Markers for Any Metadata Column
```python
# Cell type markers
sc_find_markers(groupby="cell_type", n_genes=100)

# Condition markers
sc_find_markers(groupby="treatment", n_genes=100)

# Time point markers
sc_find_markers(groupby="timepoint", n_genes=100)

# Sample-specific markers
sc_find_markers(groupby="sample_id", n_genes=100)
```

#### One-vs-Rest Analysis (Specific Clusters)
```python
# Find markers for specific clusters only
sc_find_markers_vs_rest(
    groupby="leiden",
    groups=["0", "3", "5"],  # Only analyze these clusters
    reference="rest",        # Compare against all other cells
    n_genes=100
)

# Or compare against a specific reference group
sc_find_markers_vs_rest(
    groupby="cell_type",
    groups=["T_cells", "B_cells"],
    reference="Fibroblasts",
    n_genes=100
)
```

#### Pseudobulk DEG Analysis (DESeq2)
```python
# Robust DEG analysis with biological replicates
sc_pseudobulk_deg(
    sample_key="sample_id",      # Column with sample/replicate IDs
    condition_key="condition",   # Column with condition labels
    condition1="Control",
    condition2="Treatment"
)

# Cell type-specific pseudobulk analysis
sc_pseudobulk_deg(
    sample_key="sample_id",
    condition_key="treatment",
    condition1="Vehicle",
    condition2="Drug",
    cell_type_key="cell_type",
    cell_type="T_cell"           # Only analyze T cells
)

# Visualize results
sc_plot_volcano(key="pseudobulk_deg", pval_cutoff=0.05, logfc_cutoff=1.0)
sc_plot_ma(key="pseudobulk_deg", top_genes=15)
```

## Tool Details

### DEG Analysis Tools

**Three complementary approaches:**

1. **sc_find_markers** - All-vs-all marker discovery
   - Finds markers distinguishing each group from all others
   - Best for: Initial cluster characterization
   - Methods: wilcoxon (default), t-test, logreg

2. **sc_compare_groups** - Two-group direct comparison
   - Compares two specific groups (e.g., Young vs Aged)
   - Shows upregulated/downregulated genes with direction
   - Best for: Condition comparisons, treatment effects

3. **sc_find_markers_vs_rest** - One-vs-rest analysis
   - Each group vs all other cells combined
   - Can specify custom reference group
   - Best for: Group-specific markers against background

4. **sc_pseudobulk_deg** - Pseudobulk DEG with DESeq2
   - Aggregates single-cell counts by sample for robust statistics
   - Requires biological replicates (min 2 per condition)
   - Best for: Publication-quality DEG with proper statistical inference
   - Handles batch effects and sample-level variation

**DEG Visualization:**
- **sc_plot_volcano** - Volcano plot with significance thresholds
- **sc_plot_ma** - MA plot for expression vs fold change

### Harmony Integration

**Batch effect correction features:**
- `sc_check_batch_effect` - Diagnostic visualization
- `sc_harmony_integrate` - Harmony algorithm
  - theta parameter: 0-4 (higher = more aggressive)
  - Preserves biological variation while removing batch effects

### Subset Tools

**Extract specific populations for focused analysis:**

```python
# Subset by cluster IDs
sc_subset_clusters(
    cluster_key="leiden",
    clusters=["0", "3", "5"]  # Keep only these clusters
)

# Subset by metadata conditions
sc_subset_cells(
    condition="cell_type == 'T_cell' and age == 'Young'"
)

# Or using dict syntax
sc_subset_cells(
    conditions={"cell_type": "T_cell", "condition": ["Control", "Treatment"]}
)
```

## Complete Workflow Examples

### Example 1: Aging Study
```python
# Standard preprocessing
sc_load_h5ad("aging_data.h5ad")
sc_quality_control()
sc_normalize()
sc_find_hvg()
sc_compute_pca()
sc_compute_umap()
sc_leiden_clustering()

# Find cluster markers
sc_find_markers(groupby="leiden")

# Compare age groups
sc_compare_groups(groupby="age_group", group1="Young", group2="Aged")

# Export and visualize
sc_export_deg(output_dir="/results/aging", format="both")
sc_plot_deg_heatmap(n_genes=20, save_path="/results/aging/heatmap.png")
```

### Example 2: Multi-batch Integration
```python
# Preprocessing
sc_load_h5ad("multi_batch.h5ad")
sc_quality_control()
sc_normalize()
sc_find_hvg()
sc_compute_pca()

# Batch correction
sc_check_batch_effect(batch_key="batch")
sc_harmony_integrate(batch_key="batch", theta=2.0)

# Downstream analysis on corrected data
sc_compute_umap(use_rep="X_pca_harmony")
sc_leiden_clustering()
sc_find_markers(groupby="leiden")
```

### Example 3: Load Multiple 10X Samples
```python
# Auto-detect samples and metadata from folder names
sc_load_10x_multi(data_dir="/data/10x_samples/")

# Review auto-detection results, then proceed
sc_quality_control()
sc_normalize()
sc_find_hvg()
sc_compute_pca()

# Check and correct batch effects
sc_check_batch_effect(batch_key="sample_id")
sc_harmony_integrate(batch_key="sample_id")

# Continue analysis
sc_compute_umap(use_rep="X_pca_harmony")
sc_leiden_clustering()
```

### Example 4: Focused Subset Analysis
```python
# After initial clustering, extract T cells for deeper analysis
sc_subset_clusters(
    cluster_key="cell_type",
    clusters=["CD4_T", "CD8_T", "Treg"]
)

# Re-run analysis on subset
sc_compute_pca(adata_path="/tmp/sc_subset_CD4_T_CD8_T_Treg.h5ad")
sc_compute_umap()
sc_leiden_clustering(resolution=0.8)  # Higher resolution for sub-clustering
sc_find_markers()
```

## Dependencies

- Python ≥3.11
- scanpy ≥1.10.0
- anndata ≥0.10.0
- harmonypy ≥0.0.9
- pydeseq2 ≥0.4.0
- pandas ≥2.0.0
- numpy ≥1.24.0, <2.3
- matplotlib ≥3.7.0
- seaborn ≥0.12.0
- scipy ≥1.11.0
- openpyxl ≥3.1.0

## License

MIT
