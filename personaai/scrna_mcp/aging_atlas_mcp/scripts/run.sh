#!/bin/bash

# Enhanced Aging Atlas MCP Server runner script

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project paths
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_PATH="${PROJECT_ROOT}/src"
SERVER_MODULE="aging_atlas_mcp.server"

echo -e "${BLUE}🚀 Aging Atlas TileDB-SOMA MCP Server${NC}"
echo "=================================================="

# Function to check Python environment
check_python() {
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}❌ Python 3 not found${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✅ Python 3 available${NC}"
}

# Function to check dependencies
check_dependencies() {
    echo -e "${YELLOW}📦 Checking dependencies...${NC}"
    
    cd "$PROJECT_ROOT"
    export PYTHONPATH="${SRC_PATH}:${PYTHONPATH}"
    
    python3 -c "
import sys
sys.path.insert(0, '${SRC_PATH}')

packages = ['fastmcp', 'tiledbsoma', 'pandas']
missing = []

for pkg in packages:
    try:
        __import__(pkg)
        print(f'✅ {pkg}')
    except ImportError:
        print(f'❌ {pkg}')
        missing.append(pkg)

if missing:
    print()
    print('💡 Install missing packages:')
    print(f'pip install {\" \".join(missing)}')
    sys.exit(1)
" 2>/dev/null

    if [ $? -ne 0 ]; then
        echo -e "${RED}⚠️  Dependencies check failed${NC}"
        echo "Run: pip install fastmcp tiledbsoma pandas"
        exit 1
    fi
}

# Function to run tests
run_tests() {
    echo -e "${YELLOW}🧪 Running tests...${NC}"
    cd "$PROJECT_ROOT"
    export PYTHONPATH="${SRC_PATH}:${PYTHONPATH}"
    python3 tests/test_server.py
}

# Function to start development server
start_dev_server() {
    echo -e "${YELLOW}🔧 Starting development server...${NC}"
    echo "MCP Inspector will be available at: http://localhost:6274"
    
    cd "$PROJECT_ROOT"
    export PYTHONPATH="${SRC_PATH}:${PYTHONPATH}"
    
    if command -v fastmcp &> /dev/null; then
        fastmcp dev -m "${SERVER_MODULE}"
    else
        echo -e "${RED}❌ fastmcp command not found${NC}"
        echo "Install with: pip install fastmcp"
        exit 1
    fi
}

# Function to start production server
start_prod_server() {
    echo -e "${YELLOW}📡 Starting production server (STDIO mode)...${NC}"
    
    cd "$PROJECT_ROOT"
    export PYTHONPATH="${SRC_PATH}:${PYTHONPATH}"
    python3 -m "${SERVER_MODULE}"
}

# Function to show help
show_help() {
    echo "Usage: $0 [COMMAND]"
    echo
    echo "Commands:"
    echo "  dev     Start development server with MCP Inspector"
    echo "  prod    Start production server (STDIO mode for Claude)"
    echo "  test    Run test suite"
    echo "  check   Check dependencies and configuration"
    echo "  help    Show this help message"
    echo
    echo "Examples:"
    echo "  $0 dev    # Start with web inspector at localhost:6274"
    echo "  $0 test   # Run all tests"
    echo "  $0 prod   # Start for Claude Desktop integration"
}

# Main logic
main() {
    case "${1:-prod}" in
        "dev"|"development")
            check_python
            check_dependencies
            start_dev_server
            ;;
        "prod"|"production"|"")
            check_python
            check_dependencies
            start_prod_server
            ;;
        "test")
            check_python
            check_dependencies
            run_tests
            ;;
        "check")
            check_python
            check_dependencies
            echo -e "${GREEN}✅ All checks passed${NC}"
            ;;
        "help"|"-h"|"--help")
            show_help
            ;;
        *)
            echo -e "${RED}❌ Unknown command: $1${NC}"
            echo
            show_help
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
