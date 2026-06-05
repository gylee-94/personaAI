import asyncio
from pathlib import Path

import anndata as ad
import numpy as np
import pandas as pd

from sc_analysis_mcp.tools.aging_analysis import sc_aging_deg


def test_sc_aging_deg_handles_single_gene_dataset(tmp_path: Path):
    h5ad_path = tmp_path / "single_gene_aging.h5ad"

    obs = pd.DataFrame(
        {
            "Sex": [
                "Male", "Male", "Male", "Male", "Male", "Male",
                "Female", "Female", "Female", "Female", "Female", "Female",
            ],
            "Age_group": [
                "03_months", "03_months", "03_months", "23_months", "23_months", "23_months",
                "03_months", "03_months", "03_months", "23_months", "23_months", "23_months",
            ],
            "Genotype": ["WT"] * 12,
        },
        index=[f"cell{i}" for i in range(12)],
    )
    var = pd.DataFrame(index=["Cirbp"])
    x = np.array([[1], [2], [1], [10], [11], [12], [2], [1], [2], [8], [9], [10]], dtype=float)

    ad.AnnData(X=x, obs=obs, var=var).write_h5ad(h5ad_path)

    result = asyncio.run(
        sc_aging_deg(
            {
                "adata_path": str(h5ad_path),
                "young_groups": ["03_months"],
                "old_groups": ["23_months"],
                "save_path": str(tmp_path / "aging_deg.png"),
            }
        )
    )

    assert "❌" not in result
    assert "Up in Old" in result
