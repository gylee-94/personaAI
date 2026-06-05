"""
Setup configuration for Aging Atlas MCP Server
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README file
readme_path = Path(__file__).parent / "docs" / "README.md"
long_description = readme_path.read_text(encoding="utf-8") if readme_path.exists() else ""

# Read requirements
requirements_path = Path(__file__).parent / "requirements.txt"
requirements = []
if requirements_path.exists():
    requirements = [
        line.strip() 
        for line in requirements_path.read_text().splitlines() 
        if line.strip() and not line.startswith("#")
    ]

setup(
    name="aging-atlas-mcp",
    version="1.0.0",
    description="FastMCP server for accessing Mouse Aging Atlas single-cell data via TileDB-SOMA",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Aging Atlas MCP Team",
    author_email="your.email@example.com",
    url="https://github.com/your-username/aging-atlas-mcp",
    
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    
    python_requires=">=3.8",
    install_requires=requirements,
    
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "black>=22.0.0",
            "flake8>=4.0.0",
        ],
        "viz": [
            "matplotlib>=3.5.0",
            "seaborn>=0.11.0",
            "scanpy>=1.9.0",
        ]
    },
    
    entry_points={
        "console_scripts": [
            "aging-atlas-mcp=aging_atlas_mcp.server:main",
        ],
    },
    
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Scientific/Engineering :: Bio-Informatics",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    
    keywords="mcp, single-cell, genomics, aging, tiledb, soma, bioinformatics",
    
    project_urls={
        "Bug Reports": "https://github.com/your-username/aging-atlas-mcp/issues",
        "Source": "https://github.com/your-username/aging-atlas-mcp",
        "Documentation": "https://github.com/your-username/aging-atlas-mcp/blob/main/docs/README.md",
    },
)
