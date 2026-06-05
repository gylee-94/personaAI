# 🚀 Quick Start Guide

Get the Aging Atlas MCP Server running in 5 minutes!

## ⚡ Installation

```bash
# 1. Navigate to project
cd aging_atlas_mcp

# 2. Install dependencies
pip install -r requirements.txt

# 3. Make scripts executable
chmod +x scripts/run.sh
```

## 🧪 Test Everything

```bash
# Run comprehensive test suite
./scripts/run.sh test
```

Expected output:
```
✅ FastMCP available
✅ TileDB-SOMA available  
✅ Data path exists: ${SOMA_BASE_PATH}
✅ MCP server created successfully
🎉 All tests passed! Server is ready
```

## 🔧 Development Mode

Start with MCP Inspector for interactive testing:

```bash
./scripts/run.sh dev
```

Then open: **http://localhost:6274**

### Test Commands in Inspector
```javascript
// List experiments
soma_list_experiments()

// Explore brain data
soma_open_experiment("Brain")

// Get cell types
soma_explore_cell_types("Heart")

// Preview filtered T cells
soma_to_anndata_for_screening(
  "Heart",
  obs_value_filter="Main_cell_type == 'T cell'",
  max_cells=500
)
```

## 🤖 Claude Desktop Setup

### 1. Find Configuration File

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

### 2. Add Configuration

```json
{
  "mcpServers": {
    "aging-atlas": {
      "command": "python3",
      "args": ["/FULL/PATH/TO/aging_atlas_mcp/src/aging_atlas_mcp/server.py"],
      "env": {
        "PYTHONPATH": "/FULL/PATH/TO/aging_atlas_mcp/src"
      }
    }
  }
}
```

### 3. Restart Claude Desktop

**Important**: Complete restart, not just refresh!

### 4. Verify Connection

Look for 🔨 hammer icon in Claude chat input. If missing:
- Check paths are absolute
- Verify JSON syntax
- Check logs: `~/Library/Logs/Claude/`

## 💬 Claude Usage Examples

Once connected, try these prompts:

### Basic Exploration
```
"Show me all available experiments in the aging atlas"
"What's the metadata for the Brain experiment?"
"What cell types are in the Heart experiment?"
```

### Filtered Queries
```
"Get me data for T cells from 3-month-old mice in the Heart experiment"
"Show me microglia cells from the Brain experiment"
"Find all B cells with high UMI counts"
```

### Gene Analysis
```
"Look for Apoe, Trem2, and Cd68 genes in the Brain experiment"  
"Convert microglia cells to AnnData format"
"Show me filtering examples I can use"
```

## 🆘 Quick Troubleshooting

### ❌ Tests Fail
```bash
# Check dependencies
pip install fastmcp tiledbsoma pandas

# Check data path
ls "${SOMA_BASE_PATH:-./soma_data}/"
```

### ❌ Claude Not Connecting
1. Use **absolute paths** in config
2. Check JSON syntax with jsonlint
3. Restart Claude completely
4. Check error logs

### ❌ MCP Inspector Won't Start
```bash
# Install fastmcp CLI
pip install "fastmcp[cli]"

# Or run directly
PYTHONPATH=src python3 src/aging_atlas_mcp/server.py
```

## 📋 Next Steps

✅ Tests passing? **Ready for production!**  
✅ MCP Inspector working? **Try all tools**  
✅ Claude connected? **Start exploring data!**  

Check out the full [API Documentation](API.md) for advanced usage.

---

**Need help?** Check the main [README.md](README.md) for detailed troubleshooting.
