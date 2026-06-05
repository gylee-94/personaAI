"""Compatibility helpers for reading h5ad files from mixed AnnData versions."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path


def read_h5ad_compat(file_path: str):
    """Read h5ad files, tolerating legacy null /uns/log1p/base metadata."""
    import scanpy as sc

    try:
        return sc.read_h5ad(file_path)
    except Exception as exc:
        if not _has_null_log1p_base(file_path):
            raise

        tmp_path = _copy_without_null_log1p_base(file_path)
        try:
            return sc.read_h5ad(tmp_path)
        except Exception as retry_exc:
            raise retry_exc from exc
        finally:
            try:
                os.unlink(tmp_path)
            except FileNotFoundError:
                pass


def _has_null_log1p_base(file_path: str) -> bool:
    import h5py

    try:
        with h5py.File(file_path, "r") as handle:
            if "uns/log1p/base" not in handle:
                return False
            base = handle["uns/log1p/base"]
            return base.attrs.get("encoding-type") == "null"
    except OSError:
        return False


def _copy_without_null_log1p_base(file_path: str) -> str:
    import h5py

    source = Path(file_path)
    with tempfile.NamedTemporaryFile(
        prefix=f"{source.stem}_compat_",
        suffix=".h5ad",
        delete=False,
    ) as tmp:
        tmp_path = tmp.name

    shutil.copy2(file_path, tmp_path)
    with h5py.File(tmp_path, "r+") as handle:
        if "uns/log1p/base" in handle:
            del handle["uns/log1p/base"]
    return tmp_path
