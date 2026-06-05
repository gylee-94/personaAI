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

"""Phase 3: Clustering tools"""
import logging
from ..h5ad_compat import read_h5ad_compat

logger = logging.getLogger("sc-analysis-mcp.clustering")


async def sc_rename_clusters(arguments: dict) -> str:
    """Rename or merge cluster labels with a user-defined mapping"""
    adata_path = arguments.get("adata_path", "/tmp/sc_umap.h5ad")
    cluster_key = arguments.get("cluster_key", "leiden")
    mapping = arguments.get("mapping", {})
    new_key = arguments.get("new_key", None)
    output_path = arguments.get("output_path", None)

    try:
        import scanpy as sc

        if not mapping:
            return "❌ 'mapping' is required. e.g. {\"2\": \"NK cell\", \"4\": \"NK cell\"}"

        adata = read_h5ad_compat(adata_path)

        if cluster_key not in adata.obs.columns:
            available = list(adata.obs.columns)
            return f"❌ Column '{cluster_key}' not found.\nAvailable columns: {available}"

        # Before stats
        before = adata.obs[cluster_key].value_counts().sort_index()

        # Apply mapping — keep original value if not in mapping
        col = adata.obs[cluster_key].astype(str)
        renamed = col.map(lambda x: str(mapping.get(x, mapping.get(int(x), x)) if x.lstrip('-').isdigit() else mapping.get(x, x)))

        target_key = new_key if new_key else cluster_key
        adata.obs[target_key] = renamed.astype("category")

        # After stats
        after = adata.obs[target_key].value_counts().sort_index()

        # Build diff summary
        mapping_str = "\n".join([f"   '{k}' → '{v}'" for k, v in mapping.items()])
        after_str = "\n".join([f"   {c}: {cnt:,} cells" for c, cnt in after.items()])

        # Detect merges (multiple keys mapping to same value)
        from collections import defaultdict
        reverse = defaultdict(list)
        for k, v in mapping.items():
            reverse[str(v)].append(str(k))
        merges = {v: ks for v, ks in reverse.items() if len(ks) > 1}
        merge_str = ""
        if merges:
            merge_str = "\n🔀 Merged clusters:\n" + "\n".join(
                [f"   {', '.join(ks)} → '{v}'" for v, ks in merges.items()]
            )

        out = output_path if output_path else adata_path
        adata.write_h5ad(out)

        mode = f"new column '{target_key}'" if new_key else f"column '{cluster_key}' (overwritten)"

        result = f"""✏️ Cluster Rename Complete!

📋 Applied mapping:
{mapping_str}{merge_str}

📊 Result saved to {mode}:
{after_str}

💾 {out}
🎯 Next: sc_plot_umap(color='{target_key}') to visualize"""

        return result

    except Exception as e:
        logger.error(f"Rename clusters error: {e}", exc_info=True)
        return f"❌ {e}"

async def sc_leiden_clustering(arguments: dict) -> str:
    """Leiden/Louvain clustering algorithm"""
    adata_path = arguments.get("adata_path", "/tmp/sc_umap.h5ad")
    resolution = arguments.get("resolution", 0.5)
    
    try:
        import scanpy as sc
        
        adata = read_h5ad_compat(adata_path)
        
        # Try leiden first, fallback to louvain if not available
        try:
            sc.tl.leiden(adata, resolution=resolution)
            cluster_key = 'leiden'
            method = 'Leiden'
        except (ImportError, ModuleNotFoundError):
            logger.info("Leiden not available, using Louvain instead")
            sc.tl.louvain(adata, resolution=resolution)
            cluster_key = 'louvain'
            method = 'Louvain'
        
        n_clusters = adata.obs[cluster_key].nunique()
        cluster_sizes = adata.obs[cluster_key].value_counts().sort_index()
        
        # Show cluster distribution
        size_str = "\n".join([
            f"   Cluster {c}: {cnt:,} cells" 
            for c, cnt in cluster_sizes.head(10).items()
        ])
        
        out = "/tmp/sc_clustered.h5ad"
        adata.write_h5ad(out)
        
        result = f"""🔍 {method} Clustering Complete!
📊 Resolution: {resolution}
✅ Number of clusters: {n_clusters}
🏘️ Cluster distribution:
{size_str}
💾 {out}
🎯 Next: sc_plot_umap with color='{cluster_key}'"""
        
        return result
    except Exception as e:
        logger.error(f"Clustering error: {e}", exc_info=True)
        return f"❌ {e}"
