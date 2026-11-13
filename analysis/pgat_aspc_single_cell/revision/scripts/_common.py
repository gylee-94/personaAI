"""Shared paths and helpers for the Figure 4 (PGAT) mouse-level revision analyses.

Inputs (not redistributed; obtain from the Mouse Aging Atlas, GEO GSE247719):
  PERSONAAI_SOMA         folder with the TileDB-SOMA experiments; gWAT_experiment is read (X layer 'raw_counts').
                         Used by 01 (all wild-type gWAT cells; Figure 4D).
  PERSONAAI_FIGURE_DATA  folder holding Fig4_PGAT/raw.data/gWAT_{male,female}_30k.h5ad, the 30,000-cell wild-type
                         subsets (6,000 cells per age group and sex) used for Figure 4E-G. Used by 05.
Intermediate tables are written to ../intermediate (re-created when deleted); results to ../results.
"""
import os
from pathlib import Path

import pandas as pd

REVISION = Path(__file__).resolve().parents[1]
INTER = REVISION / "intermediate"
RESULTS = REVISION / "results"
INTER.mkdir(exist_ok=True)
RESULTS.mkdir(exist_ok=True)

AGE = {"03_months": 3, "06_months": 6, "12_months": 12, "16_months": 16, "23_months": 23}
VEC = "Vascular endothelial cells"
ASPC = "Adipoce stem and progenitor cells"   # spelling as annotated in the atlas


def _env(name: str) -> Path:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Set {name} (see ../README.md).")
    return Path(value)


def soma_base() -> Path:
    return _env("PERSONAAI_SOMA")


def fig4_subset(sex: str) -> Path:
    """sex: 'male' or 'female'."""
    return _env("PERSONAAI_FIGURE_DATA") / f"Fig4_PGAT/raw.data/gWAT_{sex}_30k.h5ad"


def load_obs(tissue):
    """Cell metadata written by 01_extract_gwat_from_atlas.py; adds numeric age and batch (date_EXP barcode prefix)."""
    obs = pd.read_parquet(INTER / f"{tissue}_obs.parquet")
    obs["age"] = obs.Age_group.astype(str).map(AGE)
    obs["batch"] = obs.cell_barcode.str.split("_").str[:2].str.join("_")
    return obs
