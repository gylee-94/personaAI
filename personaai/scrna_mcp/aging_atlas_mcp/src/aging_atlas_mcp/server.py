"""
Main server module for Aging Atlas TileDB-SOMA MCP Server.
"""

import json
import shutil
from pathlib import Path
from typing import Optional, Tuple

from fastmcp import FastMCP
import numpy as np
import pandas as pd
import tiledbsoma

try:
    from .config import (
        AVAILABLE_TISSUES,
        DEFAULT_SAMPLE_SIZE,
        MAX_SAMPLE_SIZE,
        SERVER_NAME,
        get_experiment_path,
        validate_experiment,
    )
except ImportError:
    from aging_atlas_mcp.config import (
        AVAILABLE_TISSUES,
        DEFAULT_SAMPLE_SIZE,
        MAX_SAMPLE_SIZE,
        SERVER_NAME,
        get_experiment_path,
        validate_experiment,
    )


DEFAULT_PREVIEW_SIZE = 1000
DEFAULT_H5AD_PATH = "/tmp/aging_analysis/aging_data.h5ad"
PRKDC_EXCLUSION_FILTER = "Genotype != 'Prkdc'"


def create_mcp_server() -> FastMCP:
    """Create and configure the MCP server."""
    mcp = FastMCP(SERVER_NAME)
    _register_basic_tools(mcp)
    _register_conversion_tools(mcp)
    _register_exploration_tools(mcp)
    return mcp


def _json(data: dict) -> str:
    return json.dumps(data, default=str, indent=2)


def _normalize_filter(value: str) -> Optional[str]:
    return value or None


def _normalize_max_cells(max_cells: int) -> Optional[int]:
    return max_cells if max_cells > 0 else None


def _read_obs_sample(exp, sample_size: int):
    return exp.obs.read(coords=(slice(0, sample_size),)).concat().to_pandas()


def _read_var_sample(exp, measurement_name: str, sample_size: int):
    return exp.ms[measurement_name].var.read(coords=(slice(0, sample_size),)).concat().to_pandas()


def _apply_gene_symbols(adata) -> bool:
    """Use gene_symbol as var_names when present."""
    if "gene_symbol" not in adata.var.columns:
        return False

    adata.var_names = adata.var["gene_symbol"]
    adata.var_names_make_unique()
    return True


def _sample_obs(filtered_obs, max_cells: int, sampling_method: str, random_seed: int):
    if len(filtered_obs) <= max_cells:
        return filtered_obs, False

    if "soma_joinid" not in filtered_obs.columns:
        raise ValueError("Cannot sample cells because obs is missing soma_joinid")

    if sampling_method == "first":
        return filtered_obs.head(max_cells).copy(), True

    if sampling_method == "random" or (
        sampling_method == "stratified" and "Age_group" not in filtered_obs.columns
    ):
        rng = np.random.default_rng(random_seed)
        sampled_positions = rng.choice(len(filtered_obs), size=max_cells, replace=False)
        return filtered_obs.iloc[sampled_positions].copy(), True

    if sampling_method != "stratified":
        raise ValueError(f"Unknown sampling method: {sampling_method}")

    age_groups = filtered_obs["Age_group"].dropna().unique()
    if len(age_groups) == 0 or max_cells < len(age_groups):
        rng = np.random.default_rng(random_seed)
        sampled_positions = rng.choice(len(filtered_obs), size=max_cells, replace=False)
        return filtered_obs.iloc[sampled_positions].copy(), True

    per_group = max(1, max_cells // len(age_groups))
    sampled = filtered_obs.groupby("Age_group", observed=False, group_keys=False).apply(
        lambda group: group.sample(n=min(len(group), per_group), random_state=random_seed)
    )

    if len(sampled) < max_cells:
        remaining = filtered_obs.drop(sampled.index, errors="ignore")
        fill_count = min(max_cells - len(sampled), len(remaining))
        if fill_count > 0:
            fill = remaining.sample(n=fill_count, random_state=random_seed)
            sampled = pd.concat([sampled, fill])

    if len(sampled) > max_cells:
        sampled = sampled.sample(n=max_cells, random_state=random_seed)

    return sampled.reset_index(drop=True).copy(), True


def _build_obs_query(exp, measurement_name: str, obs_value_filter: Optional[str], max_cells: Optional[int],
                     sampling_method: str, random_seed: int):
    if not obs_value_filter and not max_cells:
        return tiledbsoma.AxisQuery(coords=(slice(0, DEFAULT_PREVIEW_SIZE),)), {
            "sampling_applied": False,
            "actual_cells_sampled": None,
        }

    obs_query = tiledbsoma.AxisQuery(value_filter=obs_value_filter) if obs_value_filter else None

    if not max_cells:
        return obs_query, {
            "sampling_applied": False,
            "actual_cells_sampled": None,
        }

    filtered_obs = exp.axis_query(measurement_name, obs_query=obs_query).obs().concat().to_pandas()
    sampled_obs, sampling_applied = _sample_obs(filtered_obs, max_cells, sampling_method, random_seed)

    if not sampling_applied:
        return obs_query, {
            "sampling_applied": False,
            "actual_cells_sampled": len(filtered_obs),
        }

    sampled_joinids = sampled_obs["soma_joinid"].tolist()
    joinid_filter = f"soma_joinid in {sampled_joinids}"
    combined_filter = f"({obs_value_filter}) and ({joinid_filter})" if obs_value_filter else joinid_filter

    return tiledbsoma.AxisQuery(value_filter=combined_filter), {
        "sampling_applied": True,
        "actual_cells_sampled": len(sampled_obs),
    }


def _load_anndata(exp, measurement_name: str, X_name: str, obs_value_filter: str,
                  var_value_filter: str, max_cells: int, sampling_method: str, random_seed: int):
    obs_filter = _normalize_filter(obs_value_filter)
    var_filter = _normalize_filter(var_value_filter)
    cell_limit = _normalize_max_cells(max_cells)

    obs_query, sampling = _build_obs_query(
        exp,
        measurement_name,
        obs_filter,
        cell_limit,
        sampling_method,
        random_seed,
    )
    var_query = tiledbsoma.AxisQuery(value_filter=var_filter) if var_filter else None
    query = exp.axis_query(measurement_name, obs_query=obs_query, var_query=var_query)
    adata = query.to_anndata(X_name=X_name)
    gene_symbols_applied = _apply_gene_symbols(adata)

    return adata, {
        "obs_filter": obs_filter,
        "var_filter": var_filter,
        "max_cells": cell_limit,
        "sampling_method": sampling_method if sampling["sampling_applied"] else None,
        "gene_symbols_applied": gene_symbols_applied,
        **sampling,
    }


def _with_prkdc_excluded(exp, obs_value_filter: str) -> str:
    obs_sample = _read_obs_sample(exp, 1)
    if "Genotype" not in obs_sample.columns:
        return obs_value_filter

    if not obs_value_filter:
        return PRKDC_EXCLUSION_FILTER

    return f"({obs_value_filter}) and ({PRKDC_EXCLUSION_FILTER})"


def _adata_summary(adata) -> dict:
    return {
        "shape": adata.shape,
        "obs_columns": list(adata.obs.columns),
        "var_columns": list(adata.var.columns),
        "X_type": str(type(adata.X)),
    }


def _prepare_output_path(h5ad_path: str) -> Tuple[Path, Optional[Path]]:
    requested_path = Path(h5ad_path)
    if h5ad_path.startswith("/tmp/aging_analysis/"):
        output_path = requested_path
        final_path = None
    else:
        output_path = Path(DEFAULT_H5AD_PATH)
        final_path = requested_path

    output_path.parent.mkdir(parents=True, exist_ok=True)
    return output_path, final_path


def _copy_to_requested_path(output_path: Path, final_path: Optional[Path]) -> Path:
    if final_path is None:
        return output_path

    final_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(output_path, final_path)
    return final_path


def _register_basic_tools(mcp: FastMCP) -> None:
    """Register basic experiment access tools."""

    @mcp.tool()
    def soma_list_experiments() -> str:
        """사용 가능한 Aging Atlas 실험 목록 조회"""
        return _json({
            "experiments": AVAILABLE_TISSUES,
            "total_count": len(AVAILABLE_TISSUES),
            "description": "Mouse Aging Atlas experiments by tissue type",
        })

    @mcp.tool()
    def soma_open_experiment(experiment_name: str) -> str:
        """TileDB-SOMA Experiment 열기 및 샘플 기반 기본 정보 반환"""
        if not validate_experiment(experiment_name):
            return _json({
                "error": f"Experiment '{experiment_name}' not found or path doesn't exist",
                "available_experiments": AVAILABLE_TISSUES,
            })

        try:
            exp_path = get_experiment_path(experiment_name)

            with tiledbsoma.Experiment.open(exp_path) as exp:
                obs_sample = _read_obs_sample(exp, DEFAULT_PREVIEW_SIZE)
                measurements = list(exp.ms.keys())

                info = {
                    "experiment_name": experiment_name,
                    "experiment_path": exp_path,
                    "obs_sample_shape": obs_sample.shape,
                    "obs_columns": list(obs_sample.columns),
                    "preview_size": DEFAULT_PREVIEW_SIZE,
                    "measurements": measurements,
                    "success": True,
                }

                if "RNA" in exp.ms:
                    var_sample = _read_var_sample(exp, "RNA", DEFAULT_PREVIEW_SIZE)
                    info["var_sample_shape"] = var_sample.shape
                    info["var_columns"] = list(var_sample.columns)
                    info["X_layers"] = list(exp.ms["RNA"].X.keys()) if hasattr(exp.ms["RNA"], "X") else []

            return _json(info)
        except Exception as e:
            return _json({
                "error": f"Failed to open experiment: {str(e)}",
                "experiment_name": experiment_name,
            })


def _register_conversion_tools(mcp: FastMCP) -> None:
    """Register data conversion tools."""

    @mcp.tool()
    def soma_to_anndata_for_screening(experiment_name: str, measurement_name: str = "RNA",
                                      X_name: str = "data", obs_value_filter: str = "",
                                      var_value_filter: str = "", max_cells: int = 0,
                                      sampling_method: str = "random", random_seed: int = 42) -> str:
        """Fast data screening for hypothesis validation."""
        if not validate_experiment(experiment_name):
            return _json({"error": f"Unknown or invalid experiment: {experiment_name}"})

        try:
            exp_path = get_experiment_path(experiment_name)
            with tiledbsoma.Experiment.open(exp_path) as exp:
                obs_value_filter = _with_prkdc_excluded(exp, obs_value_filter)
                adata, query_info = _load_anndata(
                    exp,
                    measurement_name,
                    X_name,
                    obs_value_filter,
                    var_value_filter,
                    max_cells,
                    sampling_method,
                    random_seed,
                )

            return _json({
                "experiment": experiment_name,
                "measurement": measurement_name,
                "X_layer": X_name,
                **query_info,
                **_adata_summary(adata),
                "obs_sample": adata.obs.head(3).to_dict("records"),
                "var_sample": adata.var.head(3).to_dict("records"),
                "success": True,
            })
        except Exception as e:
            return _json({
                "error": f"Failed to convert to AnnData: {str(e)}",
                "experiment": experiment_name,
            })

    @mcp.tool()
    def soma_to_h5ad_for_analysis(experiment_name: str, h5ad_path: str = DEFAULT_H5AD_PATH,
                                  measurement_name: str = "RNA", X_name: str = "data",
                                  obs_value_filter: str = "", var_value_filter: str = "",
                                  max_cells: int = 0, sampling_method: str = "random",
                                  random_seed: int = 42) -> str:
        """Extract data and save it as h5ad for downstream analysis."""
        if not validate_experiment(experiment_name):
            return _json({"error": f"Unknown or invalid experiment: {experiment_name}"})

        output_path = Path(h5ad_path)
        try:
            output_path, final_path = _prepare_output_path(h5ad_path)
            exp_path = get_experiment_path(experiment_name)

            with tiledbsoma.Experiment.open(exp_path) as exp:
                adata, query_info = _load_anndata(
                    exp,
                    measurement_name,
                    X_name,
                    obs_value_filter,
                    var_value_filter,
                    max_cells,
                    sampling_method,
                    random_seed,
                )

            adata.write_h5ad(str(output_path))
            output_path = _copy_to_requested_path(output_path, final_path)
            file_size = output_path.stat().st_size if output_path.exists() else 0

            return _json({
                "experiment": experiment_name,
                "measurement": measurement_name,
                "X_layer": X_name,
                **query_info,
                "output_path": str(output_path),
                "file_size_mb": round(file_size / (1024 * 1024), 2),
                "adata_shape": adata.shape,
                "obs_columns": list(adata.obs.columns),
                "var_columns": list(adata.var.columns),
                "X_type": str(type(adata.X)),
                "success": True,
                "message": f"Successfully saved {adata.shape[0]} cells x {adata.shape[1]} genes to {output_path}",
            })
        except Exception as e:
            return _json({
                "error": f"Failed to save h5ad file: {str(e)}",
                "experiment": experiment_name,
                "output_path": str(output_path),
            })


def _register_exploration_tools(mcp: FastMCP) -> None:
    """Register data exploration tools."""

    @mcp.tool()
    def soma_explore_cell_types(experiment_name: str, sample_size: int = DEFAULT_SAMPLE_SIZE) -> str:
        """실험의 세포 타입들 탐색"""
        if not validate_experiment(experiment_name):
            return _json({"error": f"Unknown or invalid experiment: {experiment_name}"})

        sample_size = min(sample_size, MAX_SAMPLE_SIZE)

        try:
            exp_path = get_experiment_path(experiment_name)
            with tiledbsoma.Experiment.open(exp_path) as exp:
                sample_obs = _read_obs_sample(exp, sample_size)

            result = {
                "experiment": experiment_name,
                "sample_size": len(sample_obs),
                "available_columns": list(sample_obs.columns),
            }

            if "Main_cell_type" in sample_obs.columns:
                result.update({
                    "unique_cell_types": sample_obs["Main_cell_type"].dropna().unique().tolist(),
                    "cell_type_counts": sample_obs["Main_cell_type"].value_counts().to_dict(),
                    "total_unique_types": sample_obs["Main_cell_type"].dropna().nunique(),
                })

            if "Age_group" in sample_obs.columns:
                result.update({
                    "age_groups": sample_obs["Age_group"].dropna().unique().tolist(),
                    "age_group_counts": sample_obs["Age_group"].value_counts().to_dict(),
                })

            if "Sex" in sample_obs.columns:
                result["sex_distribution"] = sample_obs["Sex"].value_counts().to_dict()

            return _json(result)
        except Exception as e:
            return _json({
                "error": f"Failed to explore cell types: {str(e)}",
                "experiment": experiment_name,
            })


def main() -> None:
    """Main entry point for the MCP server."""
    mcp = create_mcp_server()
    mcp.run()


if __name__ == "__main__":
    main()
