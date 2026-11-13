"""Input and output locations for the revision analyses.

PERSONAAI_FIGURE_DATA must point to the folder that holds the figure source objects:
    Fig3_Cirbp_Liver/raw.data/liver_hepatocyte_myeloid_full.h5ad      (Figure 3B; all hepatocytes and myeloid cells)
    Fig3_Cirbp_Liver/raw.data/Cirbp_categorized_with_clusters.h5ad    (Figure 3D-G; 2,372 sampled hepatocytes)
These objects are extracted from the Mouse Aging Atlas (GEO GSE247719) and are not redistributed here.
"""
import os
from pathlib import Path

REVISION = Path(__file__).resolve().parents[1]
RESULTS = REVISION / "results"
RESULTS.mkdir(exist_ok=True)


def figure_data() -> Path:
    value = os.environ.get("PERSONAAI_FIGURE_DATA")
    if not value:
        raise SystemExit("Set PERSONAAI_FIGURE_DATA to the folder holding Fig3_Cirbp_Liver/raw.data (see README.md).")
    return Path(value)


def fig3b_object() -> Path:
    return figure_data() / "Fig3_Cirbp_Liver/raw.data/liver_hepatocyte_myeloid_full.h5ad"


def fig3dg_object() -> Path:
    return figure_data() / "Fig3_Cirbp_Liver/raw.data/Cirbp_categorized_with_clusters.h5ad"
