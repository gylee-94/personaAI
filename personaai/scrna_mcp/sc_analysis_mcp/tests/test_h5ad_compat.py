from pathlib import Path
import asyncio

import anndata as ad
import h5py
import numpy as np
import pandas as pd


def _write_h5ad_with_null_log1p_base(h5ad_path: Path):
    adata = ad.AnnData(
        X=np.array([[1.0, 0.0], [0.0, 2.0]]),
        obs=pd.DataFrame(index=["cell1", "cell2"]),
        var=pd.DataFrame(index=["GeneA", "GeneB"]),
    )
    adata.uns["log1p"] = {}
    adata.write_h5ad(h5ad_path)

    with h5py.File(h5ad_path, "r+") as handle:
        log1p = handle["uns/log1p"]
        base = log1p.create_dataset("base", data=h5py.Empty("f"))
        base.attrs["encoding-type"] = "null"
        base.attrs["encoding-version"] = "0.1.0"

    with h5py.File(h5ad_path, "r") as handle:
        assert handle["uns/log1p/base"].attrs["encoding-type"] == "null"


def test_read_h5ad_compat_handles_null_log1p_base(tmp_path: Path):
    from sc_analysis_mcp.h5ad_compat import read_h5ad_compat

    h5ad_path = tmp_path / "null_log1p_base.h5ad"
    _write_h5ad_with_null_log1p_base(h5ad_path)

    loaded = read_h5ad_compat(str(h5ad_path))

    assert loaded.shape == (2, 2)
    assert list(loaded.var_names) == ["GeneA", "GeneB"]
    assert "log1p" in loaded.uns
    assert "base" not in loaded.uns["log1p"]


def test_check_status_reads_processed_h5ad_with_null_log1p_base(tmp_path: Path):
    from sc_analysis_mcp.tools.preprocessing import sc_check_status

    _write_h5ad_with_null_log1p_base(tmp_path / "sc_loaded.h5ad")

    result = asyncio.run(sc_check_status({"data_dir": str(tmp_path)}))

    assert "sc_loaded.h5ad [1. Data loaded]" in result
    assert "2 cells × 2 genes" in result
    assert "unable to read" not in result
