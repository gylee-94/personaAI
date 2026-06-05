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

"""Phase 1: Preprocessing tools for single-cell analysis"""
import logging
import os
import re
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from ..h5ad_compat import read_h5ad_compat

logger = logging.getLogger("sc-analysis-mcp.preprocessing")


# ============================================================================
# 10X Multi-Sample Loading with Auto-Detection
# ============================================================================

def _detect_10x_structure(data_dir: str, custom_pattern: Optional[str] = None) -> Tuple[str, List[Dict]]:
    """
    Detect 10X data structure and find all sample directories

    Returns:
        (structure_type, sample_info_list)
        structure_type: 'flat', 'cellranger', 'nested', 'single'
        sample_info_list: [{path, name, detected_meta}, ...]
    """
    data_path = Path(data_dir)
    samples = []

    # Check for 10X files in root directory (single sample)
    root_files = list(data_path.glob("*matrix*")) + list(data_path.glob("*barcodes*"))
    if root_files:
        return "single", [{
            "path": str(data_path),
            "name": data_path.name,
            "detected_meta": _parse_sample_name(data_path.name, custom_pattern),
        }]

    # Scan subdirectories
    for item in sorted(data_path.iterdir()):
        if not item.is_dir():
            continue

        # Pattern 1: Direct 10X files in folder (Sample1/matrix.mtx.gz)
        if list(item.glob("*matrix*")):
            samples.append({
                "path": str(item),
                "name": item.name,
                "detected_meta": _parse_sample_name(item.name, custom_pattern)
            })
            continue

        # Pattern 2: CellRanger structure (Sample1/outs/filtered_feature_bc_matrix/)
        cellranger_paths = [
            item / "outs" / "filtered_feature_bc_matrix",
            item / "outs" / "raw_feature_bc_matrix",
            item / "filtered_feature_bc_matrix",
            item / "raw_feature_bc_matrix"
        ]
        for cr_path in cellranger_paths:
            if cr_path.exists() and list(cr_path.glob("*matrix*")):
                samples.append({
                    "path": str(cr_path),
                    "name": item.name,
                    "detected_meta": _parse_sample_name(item.name, custom_pattern)
                })
                break

    if not samples:
        return "unknown", []

    # Determine structure type
    if len(samples) == 1:
        return "single", samples
    elif any("outs" in s["path"] for s in samples):
        return "cellranger", samples
    else:
        return "nested", samples


def _parse_sample_name(name: str, custom_pattern: Optional[str] = None) -> Dict[str, str]:
    """
    Auto-parse sample/folder name to extract metadata

    Handles common patterns:
    - Sample1_Control_Rep1 → {condition: Control, replicate: Rep1}
    - Young_Mouse_1 → {condition: Young, replicate: 1}
    - Patient01_PreTreatment → {timepoint: PreTreatment}
    - Ctrl_d0_rep1 → {condition: Ctrl, timepoint: d0, replicate: rep1}
    """
    meta = {"sample_id": name}
    name_lower = name.lower()

    if custom_pattern:
        try:
            match = re.search(custom_pattern, name)
        except re.error as e:
            raise ValueError(f"Invalid custom_pattern regex: {e}") from e

        if match:
            if match.groupdict():
                meta.update({k: v for k, v in match.groupdict().items() if v is not None})
            else:
                meta.update({
                    f"group_{idx}": value
                    for idx, value in enumerate(match.groups(), start=1)
                    if value is not None
                })
            return meta

    # Split by common delimiters
    parts = re.split(r'[_\-\s]+', name)

    # Condition keywords
    condition_keywords = {
        'control': 'Control', 'ctrl': 'Control', 'ctl': 'Control',
        'treatment': 'Treatment', 'treat': 'Treatment', 'treated': 'Treatment',
        'wt': 'WT', 'wildtype': 'WT', 'wild_type': 'WT',
        'ko': 'KO', 'knockout': 'KO',
        'het': 'Het', 'heterozygous': 'Het',
        'mutant': 'Mutant', 'mut': 'Mutant',
        'young': 'Young', 'aged': 'Aged', 'old': 'Aged',
        'healthy': 'Healthy', 'disease': 'Disease', 'diseased': 'Disease',
        'normal': 'Normal', 'tumor': 'Tumor', 'cancer': 'Cancer',
        'sham': 'Sham', 'vehicle': 'Vehicle', 'veh': 'Vehicle',
        'stim': 'Stimulated', 'stimulated': 'Stimulated', 'unstim': 'Unstimulated',
        'naive': 'Naive', 'activated': 'Activated',
        'male': 'Male', 'female': 'Female', 'm': 'Male', 'f': 'Female'
    }

    # Timepoint patterns
    timepoint_patterns = [
        (r'\b(d\d+)\b', 'day'),           # d0, d7, d14
        (r'\b(day\s*\d+)\b', 'day'),      # day0, day 7
        (r'\b(hr?\d+)\b', 'hour'),        # h0, hr24
        (r'\b(hour\s*\d+)\b', 'hour'),    # hour 0
        (r'\b(wk?\d+)\b', 'week'),        # w1, wk2
        (r'\b(week\s*\d+)\b', 'week'),    # week 1
        (r'\b(pre|post|baseline)\b', 'phase'),  # pre, post
        (r'\b(t\d+)\b', 'timepoint'),     # t0, t1
    ]

    # Replicate patterns
    replicate_patterns = [
        r'\b(rep\s*\d+)\b',      # rep1, rep 2
        r'\b(r\d+)\b',           # r1, r2
        r'\b(replicate\s*\d+)\b',
        r'\b(n\d+)\b',           # n1, n2
        r'[_\-](\d+)$',          # trailing number: Sample_1
    ]

    # Batch patterns
    batch_patterns = [
        r'\b(batch\s*\d+)\b',
        r'\b(b\d+)\b',
        r'\b(run\s*\d+)\b',
        r'\b(lane\s*\d+)\b',
    ]

    # Extract condition
    for part in parts:
        part_lower = part.lower()
        if part_lower in condition_keywords:
            meta["condition"] = condition_keywords[part_lower]
            break

    # Extract timepoint
    for pattern, tp_type in timepoint_patterns:
        match = re.search(pattern, name_lower)
        if match:
            meta["timepoint"] = match.group(1).replace(" ", "")
            break

    # Extract replicate
    for pattern in replicate_patterns:
        match = re.search(pattern, name_lower)
        if match:
            rep_val = match.group(1).replace(" ", "")
            # Normalize: extract number
            rep_num = re.search(r'\d+', rep_val)
            if rep_num:
                meta["replicate"] = rep_num.group()
            break

    # Extract batch
    for pattern in batch_patterns:
        match = re.search(pattern, name_lower)
        if match:
            meta["batch"] = match.group(1).replace(" ", "")
            break

    return meta


def _format_detection_summary(samples: List[Dict], structure_type: str) -> str:
    """Format auto-detection results for user review"""

    lines = []
    lines.append(f"📁 Structure detected: {structure_type}")
    lines.append(f"📊 Samples found: {len(samples)}")
    lines.append("")
    lines.append("┌─────────────────────────────────────────────────────────────")
    lines.append("│ Sample Detection Summary")
    lines.append("├─────────────────────────────────────────────────────────────")

    # Collect all detected metadata keys
    all_keys = set()
    for s in samples:
        all_keys.update(s["detected_meta"].keys())
    all_keys.discard("sample_id")
    all_keys = sorted(all_keys)

    for i, sample in enumerate(samples, 1):
        meta = sample["detected_meta"]
        meta_str = ", ".join([f"{k}={meta.get(k, '?')}" for k in all_keys if k in meta])
        if not meta_str:
            meta_str = "(no metadata detected)"
        lines.append(f"│ {i:2d}. {sample['name']}")
        lines.append(f"│     → {meta_str}")

    lines.append("└─────────────────────────────────────────────────────────────")

    # Summary statistics
    if all_keys:
        lines.append("")
        lines.append("📋 Detected metadata columns:")
        for key in all_keys:
            values = set(s["detected_meta"].get(key) for s in samples if key in s["detected_meta"])
            lines.append(f"   • {key}: {sorted(values)}")

    return "\n".join(lines)


async def sc_load_10x(arguments: dict) -> str:
    """Load single 10X Genomics sample (matrix.mtx, barcodes.tsv, features.tsv)"""
    data_dir = arguments.get("data_dir")
    gex_only = arguments.get("gex_only", True)

    if not data_dir:
        return "❌ Error: data_dir required (directory containing matrix.mtx, barcodes.tsv, features.tsv)"

    try:
        import scanpy as sc

        if not os.path.isdir(data_dir):
            return f"❌ Error: Directory not found: {data_dir}"

        files = os.listdir(data_dir)

        adata = sc.read_10x_mtx(
            data_dir,
            var_names='gene_symbols',
            cache=False,
            gex_only=gex_only
        )

        n_cells, n_genes = adata.shape
        adata.var_names_make_unique()

        out = "/tmp/sc_loaded.h5ad"
        adata.write_h5ad(out)

        mtx_files = [f for f in files if any(x in f for x in ['matrix', 'barcodes', 'features', 'genes'])]

        return f"""📂 10X Data Loaded!
📁 Source: {data_dir}
📊 {n_cells:,} cells × {n_genes:,} genes
📋 Files: {', '.join(mtx_files[:6])}
💾 {out}
🎯 Next: sc_quality_control"""

    except Exception as e:
        logger.error(f"10X load error: {e}", exc_info=True)
        if os.path.isdir(data_dir):
            files = os.listdir(data_dir)
            return f"""❌ Error loading 10X data: {e}

📁 Directory: {data_dir}
📋 Files found: {files[:10]}...

💡 Expected files:
   - matrix.mtx(.gz)
   - barcodes.tsv(.gz)
   - features.tsv or genes.tsv(.gz)"""
        return f"❌ {e}"


async def sc_load_10x_multi(arguments: dict) -> str:
    """
    Load multiple 10X samples with automatic batch/condition detection

    Auto-detects sample structure and parses folder names for metadata.
    Adds sample-specific barcode prefixes to avoid collisions.
    """
    data_dir = arguments.get("data_dir")
    metadata_file = arguments.get("metadata_file")  # Optional CSV with sample annotations
    custom_pattern = arguments.get("custom_pattern")  # Optional regex for custom parsing
    gex_only = arguments.get("gex_only", True)

    if not data_dir:
        return "❌ Error: data_dir required (parent directory containing sample folders)"

    try:
        import scanpy as sc
        import pandas as pd
        import anndata as ad

        if not os.path.isdir(data_dir):
            return f"❌ Error: Directory not found: {data_dir}"

        # Step 1: Detect structure and find samples
        structure_type, samples = _detect_10x_structure(data_dir, custom_pattern)

        if not samples:
            files = os.listdir(data_dir)[:15]
            return f"""❌ No 10X samples detected!

📁 Directory: {data_dir}
📋 Contents: {files}

💡 Expected structure:
   Option 1 (nested):
   data_dir/
   ├── Sample1/matrix.mtx.gz, barcodes.tsv.gz, features.tsv.gz
   ├── Sample2/...

   Option 2 (CellRanger):
   data_dir/
   ├── Sample1/outs/filtered_feature_bc_matrix/
   ├── Sample2/outs/filtered_feature_bc_matrix/

🔧 If single sample, use sc_load_10x instead."""

        # Step 2: Load metadata file if provided
        external_meta = {}
        if metadata_file and os.path.exists(metadata_file):
            try:
                if metadata_file.endswith('.csv'):
                    meta_df = pd.read_csv(metadata_file)
                else:
                    meta_df = pd.read_csv(metadata_file, sep='\t')

                # Assume first column is sample identifier
                id_col = meta_df.columns[0]
                for _, row in meta_df.iterrows():
                    external_meta[str(row[id_col])] = row.to_dict()
                logger.info(f"Loaded metadata for {len(external_meta)} samples from {metadata_file}")
            except Exception as e:
                logger.warning(f"Could not load metadata file: {e}")

        # Step 3: Generate detection summary for user
        detection_summary = _format_detection_summary(samples, structure_type)

        # Step 4: Load and concatenate samples
        adata_list = []
        sample_cell_counts = []

        for sample in samples:
            sample_path = sample["path"]
            sample_name = sample["name"]

            try:
                # Load sample
                adata_sample = sc.read_10x_mtx(
                    sample_path,
                    var_names='gene_symbols',
                    cache=False,
                    gex_only=gex_only
                )

                n_cells = adata_sample.n_obs
                sample_cell_counts.append((sample_name, n_cells))

                # Add barcode prefix to avoid collisions
                adata_sample.obs_names = [f"{sample_name}_{bc}" for bc in adata_sample.obs_names]

                # Add sample_id
                adata_sample.obs["sample_id"] = sample_name

                # Add detected metadata
                for key, value in sample["detected_meta"].items():
                    if key != "sample_id":
                        adata_sample.obs[key] = value

                # Override with external metadata if available
                if sample_name in external_meta:
                    for key, value in external_meta[sample_name].items():
                        if key != meta_df.columns[0]:  # Skip ID column
                            adata_sample.obs[key] = value

                adata_list.append(adata_sample)
                logger.info(f"Loaded {sample_name}: {n_cells:,} cells")

            except Exception as e:
                logger.error(f"Failed to load {sample_name}: {e}")
                return f"""❌ Error loading sample '{sample_name}': {e}

📁 Path: {sample_path}
📋 Files: {os.listdir(sample_path) if os.path.isdir(sample_path) else 'N/A'}"""

        # Step 5: Concatenate all samples
        if len(adata_list) == 1:
            adata = adata_list[0]
        else:
            adata = ad.concat(adata_list, join='outer', label='sample_id', keys=[s["name"] for s in samples])
            # Clean up duplicate sample_id column if created
            if 'sample_id-0' in adata.obs.columns:
                adata.obs.drop(columns=[c for c in adata.obs.columns if c.startswith('sample_id-')], inplace=True)

        adata.var_names_make_unique()

        # Step 6: Save
        out = "/tmp/sc_loaded.h5ad"
        adata.write_h5ad(out)

        # Step 7: Format results
        total_cells = sum(n for _, n in sample_cell_counts)
        cell_dist = "\n".join([f"   • {name}: {n:,} cells" for name, n in sample_cell_counts])

        # Get final metadata columns
        meta_cols = [c for c in adata.obs.columns if c not in ['n_genes', 'n_counts']]

        result = f"""📂 10X Multi-Sample Load Complete!

{detection_summary}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 LOAD SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📈 Total: {total_cells:,} cells × {adata.n_vars:,} genes
📦 Samples: {len(samples)}

🏷️ Cell distribution:
{cell_dist}

📋 Metadata columns added: {', '.join(meta_cols)}
🔗 Barcode format: SampleName_ATCGATCG...

💾 Saved: {out}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  REVIEW DETECTION RESULTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
If the auto-detection is incorrect, you can:

1️⃣  Provide a metadata CSV file:
    sc_load_10x_multi(
        data_dir="{data_dir}",
        metadata_file="/path/to/metadata.csv"
    )

    CSV format:
    sample_id,condition,batch,replicate
    Sample1,Control,Batch1,1
    Sample2,Treatment,Batch1,2

2️⃣  Re-run with custom pattern (advanced):
    sc_load_10x_multi(
        data_dir="{data_dir}",
        custom_pattern="(?P<condition>\\w+)_(?P<replicate>\\d+)"
    )

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 Next: sc_quality_control
"""

        return result

    except Exception as e:
        logger.error(f"10X multi-load error: {e}", exc_info=True)
        return f"❌ Error: {e}"


# ============================================================================
# Subset Functions
# ============================================================================

async def sc_subset_clusters(arguments: dict) -> str:
    """Subset specific clusters from AnnData to create focused dataset"""
    adata_path = arguments.get("adata_path", "/tmp/sc_umap.h5ad")
    cluster_key = arguments.get("cluster_key", "leiden")
    clusters = arguments.get("clusters")
    output_path = arguments.get("output_path")

    if not clusters:
        return "❌ Error: clusters parameter required (list of cluster IDs to keep)"

    try:
        import scanpy as sc

        adata = read_h5ad_compat(adata_path)

        # Validate cluster key
        if cluster_key not in adata.obs.columns:
            available = list(adata.obs.columns)[:20]
            return f"❌ Error: '{cluster_key}' not found.\nAvailable columns: {available}"

        # Convert clusters to strings
        clusters_str = [str(c) for c in clusters]
        adata.obs[cluster_key] = adata.obs[cluster_key].astype(str)

        # Validate clusters exist
        available_clusters = sorted(adata.obs[cluster_key].unique().tolist())
        invalid = [c for c in clusters_str if c not in available_clusters]
        if invalid:
            return f"""❌ Error: Clusters {invalid} not found.
Available clusters in '{cluster_key}': {available_clusters}"""

        # Subset
        n_before = adata.n_obs
        adata_subset = adata[adata.obs[cluster_key].isin(clusters_str)].copy()
        n_after = adata_subset.n_obs

        # Output path
        if output_path is None:
            cluster_suffix = '_'.join(clusters_str[:5])
            if len(clusters_str) > 5:
                cluster_suffix += f"_etc{len(clusters_str)-5}"
            output_path = f"/tmp/sc_subset_{cluster_suffix}.h5ad"

        adata_subset.write_h5ad(output_path)

        # Cluster distribution
        dist = adata_subset.obs[cluster_key].value_counts().sort_index()
        dist_str = "\n".join([f"   • Cluster {c}: {n:,} cells" for c, n in dist.items()])

        return f"""✂️ Subset Complete!

📊 Selected clusters: {', '.join(clusters_str)}
📉 Cells: {n_before:,} → {n_after:,} ({n_after/n_before*100:.1f}% retained)

🏘️ Cluster distribution:
{dist_str}

💾 Saved: {output_path}

🎯 Recommended next steps:
   1. Re-run PCA: sc_compute_pca(adata_path="{output_path}")
   2. Re-run UMAP: sc_compute_umap()
   3. Re-cluster: sc_leiden_clustering()
   4. Find new markers: sc_find_markers()"""

    except Exception as e:
        logger.error(f"Subset error: {e}", exc_info=True)
        return f"❌ {e}"


async def sc_subset_cells(arguments: dict) -> str:
    """
    Subset cells based on metadata conditions

    Supports flexible filtering:
    - Single condition: condition="cell_type == 'T_cell'"
    - Multiple conditions: conditions={"age": "Young", "batch": ["B1", "B2"]}
    """
    adata_path = arguments.get("adata_path", "/tmp/sc_umap.h5ad")
    condition = arguments.get("condition")  # String query (pandas query syntax)
    conditions = arguments.get("conditions")  # Dict of {column: value(s)}
    output_path = arguments.get("output_path")

    if not condition and not conditions:
        return """❌ Error: Provide either 'condition' (query string) or 'conditions' (dict)

Examples:
  condition="cell_type == 'T_cell'"
  condition="age == 'Young' and batch in ['B1', 'B2']"
  conditions={"cell_type": "T_cell", "age": ["Young", "Middle"]}"""

    try:
        import scanpy as sc
        import pandas as pd

        adata = read_h5ad_compat(adata_path)
        n_before = adata.n_obs

        if condition:
            # Use pandas query
            try:
                mask = adata.obs.eval(condition)
                adata_subset = adata[mask].copy()
                filter_desc = f"Query: {condition}"
            except Exception as e:
                return f"""❌ Invalid query: {condition}
Error: {e}

💡 Query syntax examples:
   - "column == 'value'"
   - "column != 'value'"
   - "column in ['val1', 'val2']"
   - "numeric_col > 100"
   - "col1 == 'A' and col2 == 'B'"

Available columns: {list(adata.obs.columns)[:15]}..."""

        else:
            # Use conditions dict
            mask = pd.Series(True, index=adata.obs.index)
            filter_parts = []

            for col, values in conditions.items():
                if col not in adata.obs.columns:
                    return f"❌ Column '{col}' not found. Available: {list(adata.obs.columns)[:15]}..."

                if isinstance(values, list):
                    mask &= adata.obs[col].isin(values)
                    filter_parts.append(f"{col} in {values}")
                else:
                    mask &= adata.obs[col] == values
                    filter_parts.append(f"{col}={values}")

            adata_subset = adata[mask].copy()
            filter_desc = ", ".join(filter_parts)

        n_after = adata_subset.n_obs

        if n_after == 0:
            return f"""❌ No cells match the filter criteria!

Filter: {filter_desc}
Total cells: {n_before:,}

💡 Check your filter values against available options."""

        # Output path
        if output_path is None:
            output_path = "/tmp/sc_subset_filtered.h5ad"

        adata_subset.write_h5ad(output_path)

        return f"""✂️ Cell Subset Complete!

🔍 Filter: {filter_desc}
📉 Cells: {n_before:,} → {n_after:,} ({n_after/n_before*100:.1f}% retained)

💾 Saved: {output_path}

🎯 Next: Re-run analysis pipeline on subset if needed"""

    except Exception as e:
        logger.error(f"Cell subset error: {e}", exc_info=True)
        return f"❌ {e}"

async def sc_load_h5ad(arguments: dict) -> str:
    """Load h5ad file with validation"""
    file_path = arguments.get("file_path")
    if not file_path:
        return "❌ Error: file_path required"
    
    try:
        import scanpy as sc
        import pandas as pd
        
        adata = read_h5ad_compat(file_path)
        n_cells, n_genes = adata.shape
        
        # Basic summary
        obs_cols = list(adata.obs.columns[:10])
        obs_str = ", ".join(obs_cols)
        
        # Check for common cell type columns
        cell_type_cols = [c for c in adata.obs.columns if any(
            x in c.lower() for x in ['cell_type', 'celltype', 'cluster', 'annotation']
        )]
        
        adata.var_names_make_unique()
        out = "/tmp/sc_loaded.h5ad"
        adata.write_h5ad(out)
        
        result = f"""📂 H5AD Loaded!
📊 {n_cells:,} cells × {n_genes:,} genes
📋 Metadata columns ({len(adata.obs.columns)}): {obs_str}...
{f'🔍 Cell type columns found: {", ".join(cell_type_cols)}' if cell_type_cols else ''}
💾 {out}
🎯 Next: sc_quality_control"""
        
        return result
    except Exception as e:
        logger.error(f"Load error: {e}", exc_info=True)
        return f"❌ {e}"


async def sc_quality_control(arguments: dict) -> str:
    """QC filtering: remove low-quality cells and genes"""
    adata_path = arguments.get("adata_path", "/tmp/sc_loaded.h5ad")
    min_genes = arguments.get("min_genes", 200)
    min_cells = arguments.get("min_cells", 3)
    max_mt = arguments.get("max_mt_percent", 20.0)
    
    try:
        import scanpy as sc
        
        adata = read_h5ad_compat(adata_path)
        n_before = adata.n_obs
        
        # QC metrics
        adata.var['mt'] = adata.var_names.str.startswith(('MT-', 'Mt-', 'mt-'))
        sc.pp.calculate_qc_metrics(adata, qc_vars=['mt'], inplace=True)
        
        # Filter cells
        sc.pp.filter_cells(adata, min_genes=min_genes)
        
        # Filter genes
        sc.pp.filter_genes(adata, min_cells=min_cells)
        
        # Filter by mitochondrial content
        if 'pct_counts_mt' in adata.obs.columns:
            adata = adata[adata.obs.pct_counts_mt < max_mt, :]
        
        removed = n_before - adata.n_obs
        out = "/tmp/sc_qc.h5ad"
        adata.write_h5ad(out)
        
        result = f"""🔬 QC Complete!
📉 Removed: {removed:,} cells ({removed/n_before*100:.1f}%)
✅ Final: {adata.n_obs:,} cells × {adata.n_vars:,} genes
⚙️ Filters:
   - Min genes/cell: {min_genes}
   - Min cells/gene: {min_cells}
   - Max MT%: {max_mt}%
💾 {out}
🎯 Next: sc_normalize"""
        
        return result
    except Exception as e:
        logger.error(f"QC error: {e}", exc_info=True)
        return f"❌ {e}"


async def sc_normalize(arguments: dict) -> str:
    """Normalize expression data (total count + log1p)"""
    adata_path = arguments.get("adata_path", "/tmp/sc_qc.h5ad")
    target = arguments.get("target_sum", 10000)
    
    try:
        import scanpy as sc
        
        adata = read_h5ad_compat(adata_path)
        
        # Store raw data
        adata.raw = adata.copy()
        
        # Normalize
        sc.pp.normalize_total(adata, target_sum=target)
        sc.pp.log1p(adata)
        
        out = "/tmp/sc_norm.h5ad"
        adata.write_h5ad(out)
        
        result = f"""📏 Normalized!
✅ Total count normalization (target={target:,})
✅ Log1p transformation
💾 {out}
🎯 Next: sc_find_hvg"""
        
        return result
    except Exception as e:
        logger.error(f"Normalization error: {e}", exc_info=True)
        return f"❌ {e}"


async def sc_find_hvg(arguments: dict) -> str:
    """Find highly variable genes"""
    adata_path = arguments.get("adata_path", "/tmp/sc_norm.h5ad")
    n_top = arguments.get("n_top_genes", 2000)
    
    try:
        import scanpy as sc
        
        adata = read_h5ad_compat(adata_path)
        
        # Find HVGs
        sc.pp.highly_variable_genes(adata, n_top_genes=n_top, flavor='seurat')
        
        n_hvg = adata.var['highly_variable'].sum()
        
        # Get top HVGs by dispersion
        top_hvgs = adata.var[adata.var['highly_variable']].sort_values(
            'dispersions_norm', ascending=False
        ).head(10).index.tolist()
        
        out = "/tmp/sc_hvg.h5ad"
        adata.write_h5ad(out)
        
        result = f"""🎯 HVG Selection Complete!
📊 Selected: {n_hvg:,} genes ({n_hvg/adata.n_vars*100:.1f}% of total)
🔝 Top HVGs: {', '.join(top_hvgs[:5])}...
💾 {out}
🎯 Next: sc_compute_pca"""
        
        return result
    except Exception as e:
        logger.error(f"HVG error: {e}", exc_info=True)
        return f"❌ {e}"


async def sc_check_status(args: dict) -> str:
    """
    Check existing processed h5ad files in /tmp to determine pipeline progress.
    Use this BEFORE starting any analysis to avoid re-running completed steps.
    """
    import glob
    from datetime import datetime

    data_dir = args.get("data_dir", "/tmp")

    # Known pipeline file patterns and their stage descriptions
    pipeline_stages = {
        "sc_loaded": "1. Data loaded",
        "sc_qc": "2. QC filtered",
        "sc_norm": "3. Normalized",
        "sc_hvg": "4. HVG selected",
        "sc_pca": "5. PCA computed",
        "sc_umap": "6. UMAP computed",
        "sc_clustered": "7. Clustered",
        "sc_annotated": "8. Cell types annotated",
    }

    h5ad_files = sorted(glob.glob(os.path.join(data_dir, "sc_*.h5ad")))

    if not h5ad_files:
        return f"""📋 No processed h5ad files found in {data_dir}
🎯 Start from: sc_load_h5ad or sc_load_10x"""

    lines = [f"📋 Existing h5ad files in {data_dir}:\n"]
    latest_stage = None
    latest_path = None

    for fpath in h5ad_files:
        fname = os.path.basename(fpath)
        stem = fname.replace(".h5ad", "")
        size_mb = os.path.getsize(fpath) / (1024 * 1024)
        mtime = datetime.fromtimestamp(os.path.getmtime(fpath)).strftime("%Y-%m-%d %H:%M")

        # Match to pipeline stage
        stage_label = None
        for key, label in pipeline_stages.items():
            if stem.startswith(key):
                stage_label = label
                latest_stage = label
                latest_path = fpath
                break

        # Quick summary from h5ad
        try:
            adata = read_h5ad_compat(fpath)
            n_cells, n_genes = adata.shape
            obs_cols = list(adata.obs.columns)
            summary = f"{n_cells:,} cells × {n_genes:,} genes"
            obs_info = f"obs: {', '.join(obs_cols[:5])}" + ("..." if len(obs_cols) > 5 else "")
        except Exception:
            summary = "unable to read"
            obs_info = ""

        marker = "✅" if stage_label else "📄"
        label_str = f" [{stage_label}]" if stage_label else ""
        lines.append(f"  {marker} {fname}{label_str}")
        lines.append(f"     {summary} | {size_mb:.1f}MB | {mtime}")
        if obs_info:
            lines.append(f"     {obs_info}")

    lines.append("")
    if latest_stage and latest_path:
        lines.append(f"🏁 Latest pipeline stage: {latest_stage}")
        lines.append(f"📂 Resume from: {latest_path}")
    lines.append(f"\n💡 Use the latest file to avoid re-running completed steps.")

    return "\n".join(lines)
