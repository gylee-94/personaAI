# Aging Atlas MCP - Gene Filtering Guide

## ⚠️ IMPORTANT: Always use `gene_symbol` for filtering genes

### ✅ Correct Usage Examples:

```python
# Single gene filtering
var_value_filter = "gene_symbol == 'Asgr1'"
var_value_filter = "gene_symbol == 'Col1a1'"
var_value_filter = "gene_symbol == 'Pdgfra'"

# Multiple genes filtering
var_value_filter = "gene_symbol in ['Asgr1', 'Col1a1', 'Pdgfra']"
var_value_filter = "gene_symbol in ['Igf1', 'Col1a1', 'Pdgfra']"

# Pattern matching (if supported by TileDB)
var_value_filter = "gene_symbol like 'Col%'"  # All collagen genes
```

### ❌ WRONG Usage (Will cause errors):

```python
# NEVER use feature_name - this column doesn't exist!
var_value_filter = "feature_name == 'Asgr1'"  # ❌ ERROR
var_value_filter = "feature_name in ['Asgr1', 'Col1a1']"  # ❌ ERROR
```

## Complete Example:

```python
# Extract Male hepatocytes expressing Asgr1 from Young and Aged groups
soma_to_h5ad_for_analysis(
    experiment_name="Liver",
    obs_value_filter="Sex == 'Male' and Main_cell_type == 'Hepatocytes' and (Age_group == '03_months' or Age_group == '23_months')",
    var_value_filter="gene_symbol == 'Asgr1'",  # ✅ Correct!
    h5ad_path="/tmp/aging_analysis/liver_asgr1.h5ad"
)
```

## Available Column Names in var (genes) DataFrame:
- `gene_symbol`: Gene symbols (e.g., 'Asgr1', 'Col1a1') - USE THIS!
- `ensembl_id`: Ensembl IDs (e.g., 'ENSMUSG00000054932')
- `gene_type`: Gene biotype (e.g., 'protein_coding')
- `soma_joinid`: Internal TileDB ID

## Available Column Names in obs (cells) DataFrame:
- `Main_cell_type`: Cell type annotation
- `Sub_cell_type`: Sub-cell type annotation
- `Sex`: 'Male' or 'Female'
- `Age_group`: '03_months', '06_months', '12_months', '16_months', '23_months'
- `sample`: Sample identifier
- `Genotype`: Genotype information
- And many others...

---
Last Updated: 2025-01-24
