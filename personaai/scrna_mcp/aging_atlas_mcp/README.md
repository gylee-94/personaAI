# Aging Atlas TileDB-SOMA MCP Server

🧬 **Production-ready MCP server for Mouse Aging Atlas single-cell genomics data**

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![FastMCP](https://img.shields.io/badge/FastMCP-2.0+-green.svg)](https://github.com/jlowin/fastmcp)
[![TileDB-SOMA](https://img.shields.io/badge/TileDB--SOMA-1.8+-orange.svg)](https://github.com/single-cell-data/TileDB-SOMA)

## 🎯 What This Is

A high-performance MCP (Model Context Protocol) server that enables Claude and other AI assistants to explore and analyze large-scale single-cell genomics data from the Mouse Aging Atlas. Built on TileDB-SOMA for lightning-fast queries across millions of cells.

**Perfect for**: Computational biologists, aging researchers, and anyone working with single-cell data who wants AI assistance.

## ✨ Key Features

- 🚀 **High Performance**: TileDB-SOMA backend handles millions of cells efficiently
- 🧬 **17 Tissue Types**: Comprehensive mouse aging atlas coverage
- 🔍 **Smart Filtering**: SQL-like queries for precise data selection
- 📊 **AnnData Compatible**: Seamless integration with Python single-cell ecosystem
- 🤖 **AI-Ready**: Purpose-built for Claude Desktop and MCP clients
- 🧪 **Production Ready**: Comprehensive tests, proper structure, error handling

## 🚀 Quick Start

```bash
# 1. Setup
git clone <this-repo>
cd aging_atlas_mcp
pip install -r requirements.txt
chmod +x scripts/run.sh

# 2. Test
./scripts/run.sh test

# 3. Try it out
./scripts/run.sh dev
# Opens MCP Inspector at http://localhost:6274
```

**Full setup guide**: [QUICKSTART.md](docs/QUICKSTART.md)

## 📁 Project Structure

```
aging_atlas_mcp/           # 🏗️  Production-ready MCP project
├── src/aging_atlas_mcp/   # 📦 Main package
│   ├── server.py          # 🖥️  MCP server implementation  
│   └── config.py          # ⚙️  Configuration management
├── tests/                 # 🧪 Comprehensive test suite
├── scripts/               # 🔧 Helper scripts
├── docs/                  # 📚 Documentation
├── config/                # 🎛️  Configuration examples
└── requirements.txt       # 📋 Dependencies
```

## 🛠️ Available Tools

### Core Operations
| Tool | Purpose | Example |
|------|---------|---------|
| `soma_list_experiments()` | List tissue types | Get all 17 available tissues |
| `soma_open_experiment("Brain")` | Open experiment preview | Access sample-based structure and columns |

### Data Exploration
| Tool | Purpose | Example |
|------|---------|---------|
| `soma_explore_cell_types("Heart")` | Summarize sampled cell types | Cell type, age, and sex distributions |

### Conversion
| Tool | Purpose | Example |
|------|---------|---------|
| `soma_to_anndata_for_screening("Heart", obs_value_filter="Main_cell_type == 'T cell'", max_cells=500)` | Preview filtered data | Small AnnData summary for screening; `Genotype == 'Prkdc'` cells are excluded automatically |
| `soma_to_h5ad_for_analysis("Brain", h5ad_path="/tmp/aging_analysis/brain.h5ad", max_cells=5000)` | Save filtered data | h5ad file for downstream analysis |

## 💬 Claude Usage Examples

Once connected to Claude Desktop:

```
"Show me all available experiments in the aging atlas"

"What cell types are in the Heart experiment?"

"Preview T cells from 3-month-old mice in the Brain experiment"

"Save a sampled Brain dataset as h5ad for downstream analysis"
```

## 🤖 Claude Desktop Setup

1. **Add to config** (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "aging-atlas": {
      "command": "python3",
      "args": ["/full/path/to/aging_atlas_mcp/src/aging_atlas_mcp/server.py"],
      "env": {
        "PYTHONPATH": "/full/path/to/aging_atlas_mcp/src"
      }
    }
  }
}
```

2. **Restart Claude Desktop** completely

3. **Look for 🔨 icon** in chat input

## 📊 Data Structure

The server expects TileDB-SOMA formatted experiments at:
```
${SOMA_BASE_PATH}/          # default: ./soma_data
├── Brain_experiment/      # Brain tissue data
├── Heart_experiment/      # Heart tissue data
├── ...                    # Other tissues
```

Each experiment contains:
- **obs**: Cell metadata (Age_group, Main_cell_type, Sex, UMI_count, etc.)
- **var**: Gene metadata (gene_symbol, gene_name, feature_type, etc.)
- **X**: Expression matrices (sparse format)

## 🧪 Testing

```bash
# Run all tests
./scripts/run.sh test

# Check specific functionality
python3 -c "from aging_atlas_mcp.config import validate_data_path; print('✅' if validate_data_path() else '❌')"
```

## 🔧 Advanced Configuration

### Environment Variables
```bash
export SOMA_BASE_PATH="/custom/path/to/soma_data"  # Custom data path
export PYTHONPATH="/path/to/aging_atlas_mcp/src"   # For imports
```

### Local File Downloads
When using `soma_to_h5ad_for_analysis` with local paths (outside `/tmp/aging_analysis/`):
- Files are first created in standard temp location
- Then automatically copied to your local path using `cp` command
- This avoids cross-device linking issues with `move_file`
- Example:
```python
# This will use cp to copy to your local directory
soma_to_h5ad_for_analysis(
    experiment_name="Brain",
    h5ad_path="/Users/yourname/data/brain_data.h5ad",  # Local path
    obs_value_filter="Age_group == '03_months'"
)
```

### Production Deployment
```bash
# Install as package
pip install -e .

# Run production server
./scripts/run.sh prod
```

## 🆘 Troubleshooting

| Issue | Solution |
|-------|----------|
| ❌ Tests fail | `pip install -r requirements.txt` |
| ❌ Data not found | Check `$SOMA_BASE_PATH` (default `./soma_data`) exists |
| ❌ Claude won't connect | Use absolute paths, restart Claude |
| ❌ Import errors | Set `PYTHONPATH=src` |

**Full troubleshooting**: [README.md](docs/README.md#troubleshooting)

## 📚 Documentation

- 📖 **[Full Documentation](docs/README.md)** - Complete setup and usage
- ⚡ **[Quick Start Guide](docs/QUICKSTART.md)** - Get running in 5 minutes  
- 🔧 **[API Reference](docs/API.md)** - Detailed tool documentation

## 🤝 Contributing

1. Fork the repo
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Add tests for new functionality
4. Ensure tests pass: `./scripts/run.sh test`
5. Submit pull request

## 📄 License

MIT License - see [LICENSE](LICENSE) file

## 🙏 Acknowledgments

- **[TileDB-SOMA](https://github.com/single-cell-data/TileDB-SOMA)** - High-performance single-cell data access
- **[FastMCP](https://github.com/jlowin/fastmcp)** - Streamlined MCP server development  
- **Mouse Aging Atlas** - Comprehensive aging genomics dataset

---

**Ready to explore aging with AI?** 🧬 Start with [QUICKSTART.md](docs/QUICKSTART.md)!
