# Aging Atlas TileDB-SOMA MCP Server

A production-ready FastMCP server providing seamless access to Mouse Aging Atlas single-cell data through TileDB-SOMA API.

## 🧬 About the Project

This MCP (Model Context Protocol) server enables Claude and other AI assistants to interact with large-scale single-cell genomics data from the Mouse Aging Atlas. Built on TileDB-SOMA for high-performance data access, it provides a standardized interface for exploring aging-related cellular changes across 17 tissue types.

### Key Features

- **🚀 High Performance**: Built on TileDB-SOMA for efficient large-scale data access
- **🔧 Production Ready**: Structured codebase with comprehensive testing
- **📊 17 Tissue Types**: BAT, B_cell, Brain, Colon, Duodenum, Heart, Ileum, Jejunum, Kidney, Liver, Lung, Muscle, Myeloid_cell, Stomach, T_cell, gWAT, iWAT
- **🎯 Smart Filtering**: Advanced query capabilities with SQL-like filtering
- **🔬 AnnData Integration**: Seamless conversion to standard single-cell formats
- **📝 Comprehensive API**: 15+ specialized tools for data exploration and analysis

## 📁 Project Structure

```
aging_atlas_mcp/
├── src/
│   └── aging_atlas_mcp/
│       ├── __init__.py          # Package initialization
│       ├── server.py            # Main MCP server implementation
│       └── config.py            # Configuration and settings
├── tests/
│   ├── __init__.py
│   └── test_server.py           # Comprehensive test suite
├── scripts/
│   └── run.sh                   # Enhanced runner script
├── docs/
│   ├── README.md                # This file
│   ├── QUICKSTART.md            # Quick setup guide
│   └── API.md                   # Detailed API documentation
├── config/
│   └── claude_desktop.json     # Claude Desktop configuration
├── requirements.txt             # Python dependencies
├── setup.py                     # Package setup
└── .gitignore                   # Git ignore rules
```

## 🚀 Quick Start

### 1. Installation

```bash
# Clone or download the project
cd aging_atlas_mcp

# Install dependencies
pip install -r requirements.txt

# Make scripts executable
chmod +x scripts/run.sh
```

### 2. Run Tests

```bash
./scripts/run.sh test
# or
python3 tests/test_server.py
```

### 3. Start Development Server

```bash
./scripts/run.sh dev
# Opens MCP Inspector at http://localhost:6274
```

### 4. Configure Claude Desktop

Copy the configuration to your Claude Desktop config file:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
```json
{
  "mcpServers": {
    "aging-atlas": {
      "command": "python3",
      "args": ["/path/to/aging_atlas_mcp/src/aging_atlas_mcp/server.py"],
      "env": {
        "PYTHONPATH": "/path/to/aging_atlas_mcp/src"
      }
    }
  }
}
```

## 🛠️ Available Tools

### Basic Operations
- `soma_list_experiments()` - List all available tissue experiments
- `soma_open_experiment(name)` - Open and inspect sample-based experiment structure

### Data Exploration
- `soma_explore_cell_types(name, sample_size)` - Discover sampled cell type distributions

### Conversion
- `soma_to_anndata_for_screening(name, obs_value_filter, var_value_filter, max_cells)` - Convert a small filtered sample to AnnData summary; `Genotype == 'Prkdc'` cells are excluded automatically
- `soma_to_h5ad_for_analysis(name, h5ad_path, obs_value_filter, var_value_filter, max_cells)` - Save filtered data as h5ad

## 💡 Usage Examples

### Basic Exploration
```python
# List available experiments
soma_list_experiments()

# Explore brain tissue
soma_open_experiment("Brain")
```

### Cell Type Analysis
```python
# Find all cell types in heart tissue
soma_explore_cell_types("Heart")

# Get T cells from 3-month-old mice
soma_to_anndata_for_screening(
    "Heart", 
    obs_value_filter="Main_cell_type == 'T cell' and Age_group == '03_months'",
    max_cells=500
)
```

### Gene Expression Analysis
```python
# Convert filtered genes to an AnnData screening summary
soma_to_anndata_for_screening(
    "Brain",
    obs_value_filter="Main_cell_type == 'Microglia'",
    var_value_filter="gene_symbol in ['Apoe', 'Trem2', 'Cd68']",
    max_cells=500
    var_value_filter="gene_symbol IN ['Apoe', 'Trem2', 'Cd68']"
)
```

## 🔧 Configuration

### Environment Variables
- `SOMA_BASE_PATH`: Path to TileDB-SOMA data (default: `./soma_data`)

### Data Requirements
- TileDB-SOMA format experiments in `{SOMA_BASE_PATH}/{tissue}_experiment/`
- Each experiment should contain:
  - `obs`: Cell metadata (Age_group, Main_cell_type, Sex, etc.)
  - `ms["RNA"]`: Gene expression measurement
  - `ms["RNA"].var`: Gene metadata
  - `ms["RNA"].X["data"]`: Expression matrix

## 🧪 Testing

The project includes comprehensive tests covering:
- Dependency verification
- Data path validation
- MCP server functionality
- TileDB-SOMA integration
- Error handling

```bash
# Run all tests
./scripts/run.sh test

# Run specific test categories
python3 -m pytest tests/ -v
```

## 🐛 Troubleshooting

### Common Issues

1. **Data Path Not Found**
   - Verify `SOMA_BASE_PATH` points to correct location
   - Check that experiment directories exist
   - Ensure proper read permissions

2. **Import Errors**
   - Install missing dependencies: `pip install -r requirements.txt`
   - Check Python version (3.8+ required)
   - Verify PYTHONPATH in scripts

3. **Claude Desktop Integration**
   - Use absolute paths in configuration
   - Restart Claude Desktop after config changes
   - Check logs in `~/Library/Logs/Claude/`

### Debug Mode
```bash
# Run with verbose logging
PYTHONPATH=src python3 -c "
from aging_atlas_mcp.server import create_mcp_server
mcp = create_mcp_server()
print('✅ Server created successfully')
"
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## 📚 API Reference

See [API.md](API.md) for detailed documentation of all available tools and their parameters.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- [TileDB-SOMA](https://github.com/single-cell-data/TileDB-SOMA) for high-performance single-cell data access
- [FastMCP](https://github.com/jlowin/fastmcp) for streamlined MCP server development
- Mouse Aging Atlas project for the comprehensive single-cell dataset
