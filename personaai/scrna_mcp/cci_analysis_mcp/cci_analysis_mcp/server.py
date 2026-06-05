#!/usr/bin/env python3
"""
CCI-Analysis-MCP Server
Cell-Cell Interaction analysis MCP for aging hypothesis validation (LIANA+ based)

5 tools for CCI analysis:
- Analysis (1): Run LIANA rank_aggregate
- Aging (1): Compare CCI Young vs Old (sex-stratified)
- Query (1): Filter specific L-R pairs / cell type pairs
- Visualization (2): Dotplot, Network diagram
"""

import asyncio
import logging
from typing import Any
from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("cci-analysis-mcp")

# Import tool implementations
from .tools.cci_tools import (
    cci_run_analysis,
    cci_compare_aging,
    cci_query_interactions,
    cci_plot_dotplot,
    cci_plot_network
)

# Create server instance
server = Server("cci-analysis-mcp")

# Define all tools
TOOLS = [
    {
        "name": "cci_run_analysis",
        "description": "Run LIANA rank_aggregate on an h5ad file for cell-cell interaction analysis. Auto-detects human/mouse, uses local L-R database cache. Input h5ad must have cell type annotations (Main_cell_type or leiden/louvain). Compatible with h5ad from sc-analysis-mcp.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "adata_path": {
                    "type": "string",
                    "description": "Path to h5ad file (from sc-analysis-mcp or Aging Atlas)"
                },
                "groupby": {
                    "type": "string",
                    "default": "Main_cell_type",
                    "description": "Cell type column in obs (e.g. 'Main_cell_type', 'Sub_cell_type', 'leiden')"
                },
                "resource_name": {
                    "type": "string",
                    "description": "L-R database name (e.g. 'mouseconsensus', 'consensus', 'cellchatdb'). Auto-detected if not specified."
                },
                "min_cells": {
                    "type": "integer",
                    "default": 10,
                    "description": "Minimum cells per cell type to include"
                },
                "expr_prop": {
                    "type": "number",
                    "default": 0.1,
                    "description": "Minimum proportion of cells expressing a gene"
                },
                "output_path": {
                    "type": "string",
                    "default": "/tmp/cci_results.h5ad",
                    "description": "Output h5ad path (liana_res stored in .uns)"
                }
            },
            "required": ["adata_path"]
        },
        "handler": cci_run_analysis
    },
    {
        "name": "cci_compare_aging",
        "description": "Compare cell-cell interactions between Young vs Old, stratified by sex. Runs LIANA separately per age×sex group and identifies gained/lost interactions with aging. Key tool for aging CCI hypothesis validation.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "adata_path": {
                    "type": "string",
                    "description": "Path to h5ad file with Age_group and Sex columns"
                },
                "groupby": {
                    "type": "string",
                    "default": "Main_cell_type",
                    "description": "Cell type column"
                },
                "young_groups": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": ["03_months"],
                    "description": "Age groups for Young (e.g. ['03_months'])"
                },
                "old_groups": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": ["23_months"],
                    "description": "Age groups for Old (e.g. ['23_months'])"
                },
                "resource_name": {
                    "type": "string",
                    "description": "L-R database name (auto-detected if omitted)"
                },
                "min_cells": {
                    "type": "integer",
                    "default": 10
                },
                "expr_prop": {
                    "type": "number",
                    "default": 0.1
                },
                "genotype": {
                    "type": "string",
                    "default": "WT",
                    "description": "Genotype filter"
                },
                "save_path": {
                    "type": "string",
                    "default": "/tmp/cci_aging_comparison.png"
                }
            },
            "required": ["adata_path"]
        },
        "handler": cci_compare_aging
    },
    {
        "name": "cci_query_interactions",
        "description": "Query specific ligand-receptor pairs or cell type pairs from LIANA results. Use after cci_run_analysis. Filter by ligand/receptor gene names and source/target cell types.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "adata_path": {
                    "type": "string",
                    "description": "Path to h5ad with liana_res in .uns"
                },
                "ligands": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter by ligand gene(s) (e.g. ['Tgfb1', 'Wnt5a'])"
                },
                "receptors": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter by receptor gene(s) (e.g. ['Tgfbr1', 'Fzd1'])"
                },
                "source_cells": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter by source cell type(s)"
                },
                "target_cells": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter by target cell type(s)"
                },
                "max_magnitude_rank": {
                    "type": "number",
                    "default": 0.05,
                    "description": "Maximum magnitude_rank threshold (lower = stronger)"
                },
                "export_path": {
                    "type": "string",
                    "description": "Optional CSV export path"
                }
            },
            "required": ["adata_path"]
        },
        "handler": cci_query_interactions
    },
    {
        "name": "cci_plot_dotplot",
        "description": "Create dotplot visualization of cell-cell interactions from LIANA results. Shows magnitude and specificity of L-R interactions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "adata_path": {
                    "type": "string",
                    "description": "Path to h5ad with liana_res in .uns"
                },
                "source_cells": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter source cell types"
                },
                "target_cells": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter target cell types"
                },
                "top_n": {
                    "type": "integer",
                    "default": 20,
                    "description": "Number of top interactions to show"
                },
                "magnitude_metric": {
                    "type": "string",
                    "default": "magnitude_rank",
                    "description": "LIANA result column used for dot color"
                },
                "specificity_metric": {
                    "type": "string",
                    "default": "specificity_rank",
                    "description": "LIANA result column used for dot size"
                },
                "save_path": {
                    "type": "string",
                    "default": "/tmp/cci_dotplot.png"
                }
            },
            "required": ["adata_path"]
        },
        "handler": cci_plot_dotplot
    },
    {
        "name": "cci_plot_network",
        "description": "Create network/chord diagram showing interaction count between cell types. Node = cell type, edge width = number of significant interactions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "adata_path": {
                    "type": "string",
                    "description": "Path to h5ad with liana_res in .uns"
                },
                "top_n": {
                    "type": "integer",
                    "default": 30,
                    "description": "Max cell type pairs to show"
                },
                "magnitude_threshold": {
                    "type": "number",
                    "default": 0.05,
                    "description": "Magnitude rank threshold for significant interactions"
                },
                "save_path": {
                    "type": "string",
                    "default": "/tmp/cci_network.png"
                }
            },
            "required": ["adata_path"]
        },
        "handler": cci_plot_network
    }
]


# Register tools with MCP server
@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name=tool["name"],
            description=tool["description"],
            inputSchema=tool["inputSchema"]
        )
        for tool in TOOLS
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    tool = next((t for t in TOOLS if t["name"] == name), None)
    if not tool:
        return [types.TextContent(type="text", text=f"❌ Unknown tool: {name}")]

    try:
        result = await tool["handler"](arguments)
        return [types.TextContent(type="text", text=result)]
    except Exception as e:
        logger.error(f"Tool {name} error: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"❌ Error in {name}: {e}")]


async def run():
    async with stdio_server() as (read_stream, write_stream):
        logger.info("CCI-Analysis-MCP server starting...")
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main():
    asyncio.run(run())


if __name__ == "__main__":
    main()
