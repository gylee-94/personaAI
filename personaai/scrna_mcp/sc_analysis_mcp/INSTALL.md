# SC-Analysis-MCP Distribution Package

This is a distribution-ready version of SC-Analysis-MCP without virtual environment files.

## Quick Installation

```bash
cd /path/to/sc_analysis_mcp
python3 -m venv .venv
.venv/bin/pip install -e .
```

## Verify Installation

```bash
# Check if all dependencies are installed
pip list | grep -E "scanpy|anndata|harmonypy"

# Test import
python -c "import sc_analysis_mcp; print('✅ Installation successful!')"
```

## Configure Claude Desktop

Add to your `claude_desktop_config.json`:

```json
"sc_analysis_mcp_260308": {
  "command": "/path/to/sc_analysis_mcp/.venv/bin/python",
  "args": [
    "-m",
    "sc_analysis_mcp.server"
  ]
}
```

## Package Contents

- `sc_analysis_mcp/` - Main package code
  - `server.py` - MCP server implementation
  - `tools/` - 21 analysis tools
- `pyproject.toml` - Project configuration and dependencies
- `README.md` - Full documentation
- `INSTALL.md` - This file

## System Requirements

- Python ≥3.11
- 2GB RAM minimum (4GB+ recommended for large datasets)
- macOS, Linux, or Windows

## Dependencies

All dependencies will be automatically installed via `pip install -e .`:

- scanpy ≥1.10.0
- anndata ≥0.10.0
- harmonypy ≥0.0.9
- pandas ≥2.0.0
- numpy ≥1.24.0, <2.3
- matplotlib ≥3.7.0
- seaborn ≥0.12.0
- scipy ≥1.11.0
- openpyxl ≥3.1.0

## Troubleshooting

### Issue: "Module not found" error
```bash
# Make sure you activated the virtual environment
source .venv/bin/activate

# Reinstall in editable mode
pip install -e .
```

### Issue: Claude Desktop doesn't recognize the server
1. Check that the path in `claude_desktop_config.json` is absolute
2. Verify Python path: `.venv/bin/python` (not `.venv/bin/python3`)
3. Restart Claude Desktop after configuration changes

### Issue: Import errors for specific packages
```bash
# Install missing package manually
pip install scanpy anndata harmonypy

# Or reinstall all dependencies
pip install -e . --force-reinstall
```

## Support

For issues and documentation, see the main README.md file.

## License

MIT
