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

"""Batch Integration tools for single-cell analysis"""
import logging
from ..h5ad_compat import read_h5ad_compat

logger = logging.getLogger("sc-analysis-mcp.integration")

async def sc_harmony_integrate(arguments: dict) -> str:
    """
    Harmony batch correction for single-cell data
    
    Harmony removes batch effects while preserving biological variation.
    Works directly on PCA embeddings - run sc_compute_pca first.
    
    Parameters:
    -----------
    adata_path : str
        Path to h5ad file (after PCA computation)
    batch_key : str
        Column name in adata.obs containing batch labels
    theta : float or list
        Diversity clustering penalty (0-4). Higher = more aggressive correction.
        Default: 2.0. Can provide list for multiple batch keys.
    sigma : float
        Width of soft kmeans clusters. Default: 0.1
    max_iter_harmony : int
        Maximum iterations. Default: 10
    use_rep : str
        Representation to use. Default: 'X_pca'
    basis : str
        Output basis name. Default: 'X_pca_harmony'
    
    Returns:
    --------
    Batch-corrected embeddings in adata.obsm[basis]
    """
    adata_path = arguments.get("adata_path", "/tmp/sc_pca.h5ad")
    batch_key = arguments.get("batch_key")
    theta = arguments.get("theta", 2.0)
    sigma = arguments.get("sigma", 0.1)
    max_iter = arguments.get("max_iter_harmony", 10)
    use_rep = arguments.get("use_rep", "X_pca")
    basis = arguments.get("basis", "X_pca_harmony")
    
    if not batch_key:
        return "❌ Error: batch_key required (column name with batch labels)"
    
    try:
        import scanpy as sc
        import harmonypy as hm
        import pandas as pd
        
        adata = read_h5ad_compat(adata_path)
        
        # Validate batch key exists
        if batch_key not in adata.obs.columns:
            available_cols = list(adata.obs.columns[:20])
            return f"❌ Error: batch_key '{batch_key}' not found in obs.\nAvailable columns: {', '.join(available_cols)}..."
        
        # Validate PCA exists
        if use_rep not in adata.obsm.keys():
            available_reps = list(adata.obsm.keys())
            return f"❌ Error: {use_rep} not found. Available: {available_reps}\n🎯 Run sc_compute_pca first!"
        
        # Get batch info before correction
        batch_counts = adata.obs[batch_key].value_counts()
        n_batches = len(batch_counts)
        
        logger.info(f"Running Harmony on {n_batches} batches...")
        
        # Run Harmony
        # harmonypy expects data_mat (n_cells x n_components) and meta_data (DataFrame)
        pca_embedding = adata.obsm[use_rep]
        meta_data = adata.obs[[batch_key]].copy()
        
        ho = hm.run_harmony(
            pca_embedding,
            meta_data,
            batch_key,
            theta=theta,
            sigma=sigma,
            max_iter_harmony=max_iter,
            verbose=False
        )
        
        # Store corrected embeddings
        adata.obsm[basis] = ho.Z_corr.T  # Transpose back to (n_cells, n_components)
        
        # Save result
        out = "/tmp/sc_harmony.h5ad"
        adata.write_h5ad(out)
        
        # Format batch info
        batch_info = "\n".join([f"   - {batch}: {count:,} cells" 
                                for batch, count in batch_counts.items()])
        
        result = f"""🎨 Harmony Integration Complete!
🧩 Corrected {n_batches} batches:
{batch_info}
⚙️ Parameters:
   - Batch key: {batch_key}
   - Theta (diversity): {theta}
   - Sigma (cluster width): {sigma}
   - Max iterations: {max_iter}
📊 Input: {use_rep} ({pca_embedding.shape[1]} PCs)
📊 Output: {basis} ({adata.obsm[basis].shape[1]} PCs)
💾 {out}
🎯 Next: sc_compute_umap (use_rep='{basis}') or sc_leiden_clustering (use_rep='{basis}')"""
        
        return result
        
    except ImportError:
        return """❌ Error: harmonypy not installed
📦 Install with: pip install harmonypy
   or: conda install -c conda-forge harmonypy"""
    except Exception as e:
        logger.error(f"Harmony error: {e}", exc_info=True)
        return f"❌ {e}"


async def sc_check_batch_effect(arguments: dict) -> str:
    """
    Quick diagnostic to check for batch effects
    
    Visualizes PCA colored by batch to assess need for integration.
    
    Parameters:
    -----------
    adata_path : str
        Path to h5ad file (after PCA)
    batch_key : str
        Column name with batch labels
    use_rep : str
        Representation to check. Default: 'X_pca'
    save_path : str
        Output plot path
    """
    adata_path = arguments.get("adata_path", "/tmp/sc_pca.h5ad")
    batch_key = arguments.get("batch_key")
    use_rep = arguments.get("use_rep", "X_pca")
    save_path = arguments.get("save_path", "/tmp/batch_effect_check.png")
    
    if not batch_key:
        return "❌ Error: batch_key required"
    
    try:
        import scanpy as sc
        import matplotlib.pyplot as plt
        
        adata = read_h5ad_compat(adata_path)
        
        if batch_key not in adata.obs.columns:
            return f"❌ Error: batch_key '{batch_key}' not found in obs"
        
        if use_rep not in adata.obsm.keys():
            return f"❌ Error: {use_rep} not found. Run sc_compute_pca first!"
        
        # Plot PCA colored by batch
        sc.pl.pca(adata, color=batch_key, show=False)
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        batch_counts = adata.obs[batch_key].value_counts()
        batch_info = "\n".join([f"   - {batch}: {count:,} cells" 
                                for batch, count in batch_counts.items()])
        
        result = f"""🔍 Batch Effect Check Complete!
📊 Batches ({len(batch_counts)}):
{batch_info}
📈 PCA plot colored by '{batch_key}'
💾 {save_path}

💡 Interpretation:
   - Distinct clusters by batch → Strong batch effect, use Harmony
   - Mixed batches → Weak/no batch effect, integration optional"""
        
        return result
        
    except Exception as e:
        logger.error(f"Batch check error: {e}", exc_info=True)
        return f"❌ {e}"
