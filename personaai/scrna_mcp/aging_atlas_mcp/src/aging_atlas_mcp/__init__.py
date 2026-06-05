"""
Aging Atlas TileDB-SOMA MCP Server

A FastMCP server for accessing Mouse Aging Atlas data through TileDB-SOMA API.
"""

__version__ = "1.0.0"
__author__ = "Aging Atlas MCP Team"

from .server import main, create_mcp_server

__all__ = ["main", "create_mcp_server"]
