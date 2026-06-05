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

"""Phase 2: Dimensionality reduction tools"""
import logging
from ..h5ad_compat import read_h5ad_compat

logger = logging.getLogger("sc-analysis-mcp.dimensionality")

async def sc_compute_pca(arguments: dict) -> str:
    """Compute PCA for dimensionality reduction"""
    adata_path = arguments.get("adata_path", "/tmp/sc_hvg.h5ad")
    n_pcs = arguments.get("n_pcs", 50)
    
    try:
        import scanpy as sc
        import numpy as np
        
        adata = read_h5ad_compat(adata_path)
        
        # Compute PCA
        sc.tl.pca(adata, n_comps=n_pcs, svd_solver='arpack')
        
        # Variance explained
        var_ratio = adata.uns['pca']['variance_ratio']
        pc1_pc2 = (var_ratio[0] + var_ratio[1]) * 100
        total_var = var_ratio.sum() * 100
        
        out = "/tmp/sc_pca.h5ad"
        adata.write_h5ad(out)
        
        result = f"""📊 PCA Complete!
✅ {n_pcs} principal components computed
📈 PC1+PC2 variance: {pc1_pc2:.1f}%
📈 Total variance explained: {total_var:.1f}%
💾 {out}
🎯 Next: sc_compute_umap"""
        
        return result
    except Exception as e:
        logger.error(f"PCA error: {e}", exc_info=True)
        return f"❌ {e}"


async def sc_compute_umap(arguments: dict) -> str:
    """Compute UMAP embedding with neighbor graph"""
    adata_path = arguments.get("adata_path", "/tmp/sc_pca.h5ad")
    n_neighbors = arguments.get("n_neighbors", 15)
    n_pcs = arguments.get("n_pcs", 40)
    use_rep = arguments.get("use_rep", "X_pca")
    
    try:
        import scanpy as sc
        
        adata = read_h5ad_compat(adata_path)
        
        # Validate representation exists
        if use_rep not in adata.obsm.keys():
            available_reps = list(adata.obsm.keys())
            return f"❌ Error: {use_rep} not found. Available: {available_reps}"
        
        # Build k-nearest neighbor graph
        sc.pp.neighbors(adata, n_neighbors=n_neighbors, n_pcs=n_pcs, use_rep=use_rep)
        
        # Compute UMAP
        sc.tl.umap(adata)
        
        out = "/tmp/sc_umap.h5ad"
        adata.write_h5ad(out)
        
        rep_info = f" (using {use_rep})" if use_rep != "X_pca" else ""
        
        result = f"""🗺️ UMAP Complete!
✅ KNN graph built (k={n_neighbors}){rep_info}
✅ PCs used: {n_pcs}
✅ UMAP coordinates computed
💾 {out}
🎯 Next: sc_leiden_clustering OR sc_plot_umap"""
        
        return result
    except Exception as e:
        logger.error(f"UMAP error: {e}", exc_info=True)
        return f"❌ {e}"
