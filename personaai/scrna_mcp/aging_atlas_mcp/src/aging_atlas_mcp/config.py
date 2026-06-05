"""
Configuration settings for Aging Atlas MCP Server
"""
import os
from pathlib import Path
from typing import List

# Data paths
SOMA_BASE_PATH = os.getenv("SOMA_BASE_PATH", "./soma_data")

# Available tissue experiments
AVAILABLE_TISSUES: List[str] = [
    "BAT", "B_cell", "Brain", "Colon", "Duodenum", "Heart",
    "Ileum", "Jejunum", "Kidney", "Liver", "Lung", "Muscle",
    "Myeloid_cell", "Stomach", "T_cell", "gWAT", "iWAT"
]

# Server settings
SERVER_NAME = "Aging Atlas TileDB-SOMA Server"
SERVER_VERSION = "1.0.0"

# Default query limits
DEFAULT_SAMPLE_SIZE = 10000
MAX_SAMPLE_SIZE = 10000
DEFAULT_COORD_RANGE = 10

def validate_data_path() -> bool:
    """Validate that the SOMA data path exists"""
    return Path(SOMA_BASE_PATH).exists()

def get_experiment_path(experiment_name: str) -> str:
    """Get the full path for an experiment"""
    return f"{SOMA_BASE_PATH}/{experiment_name}_experiment"

def validate_experiment(experiment_name: str) -> bool:
    """Validate that an experiment exists"""
    return (
        experiment_name in AVAILABLE_TISSUES and
        Path(get_experiment_path(experiment_name)).exists()
    )
