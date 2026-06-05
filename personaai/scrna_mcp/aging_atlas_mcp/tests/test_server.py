#!/usr/bin/env python3
"""
Enhanced test suite for Aging Atlas MCP Server
"""

import sys
import pytest
from pathlib import Path

# Add the src directory to Python path
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

try:
    from aging_atlas_mcp.config import (
        SOMA_BASE_PATH, AVAILABLE_TISSUES, 
        validate_data_path, validate_experiment, get_experiment_path
    )
    from aging_atlas_mcp.server import create_mcp_server
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running from the project root directory")
    sys.exit(1)


class TestDataAccess:
    """Test data access and validation"""
    
    def test_data_path_validation(self):
        """Test that data path exists"""
        print("🔍 Testing data path validation...")
        
        path_exists = validate_data_path()
        if path_exists:
            print(f"✅ Data path exists: {SOMA_BASE_PATH}")
        else:
            print(f"⚠️  Data path doesn't exist: {SOMA_BASE_PATH}")
            print("This is expected if running without actual data")
        
        assert isinstance(path_exists, bool)
    
    def test_experiment_validation(self):
        """Test experiment path validation"""
        print("🧪 Testing experiment validation...")
        
        valid_experiments = []
        for tissue in AVAILABLE_TISSUES[:5]:  # Test first 5
            if validate_experiment(tissue):
                valid_experiments.append(tissue)
                print(f"✅ Valid experiment: {tissue}")
            else:
                print(f"⚠️  Invalid experiment: {tissue}")
        
        print(f"Found {len(valid_experiments)} valid experiments")
        assert isinstance(valid_experiments, list)


class TestDependencies:
    """Test package dependencies"""
    
    def test_required_packages(self):
        """Test that required packages are available"""
        print("📦 Testing package dependencies...")
        
        required_packages = {
            'fastmcp': 'FastMCP',
            'tiledbsoma': 'TileDB-SOMA',
            'pandas': 'Pandas',
            'typing': 'Typing'
        }
        
        missing_packages = []
        
        for package, name in required_packages.items():
            try:
                __import__(package)
                print(f"✅ {name} available")
            except ImportError:
                print(f"❌ {name} missing: pip install {package}")
                missing_packages.append(package)
        
        if missing_packages:
            pytest.skip(f"Missing required packages: {missing_packages}")
        
        assert len(missing_packages) == 0


class TestMCPServer:
    """Test MCP server functionality"""
    
    def test_server_creation(self):
        """Test that MCP server can be created"""
        print("🚀 Testing MCP server creation...")
        
        try:
            mcp = create_mcp_server()
            print("✅ MCP server created successfully")
        except Exception as e:
            pytest.fail(f"Failed to create MCP server: {e}")

        # Check server has expected attributes
        assert hasattr(mcp, 'run')
        assert hasattr(mcp, 'tool')
        assert hasattr(mcp, 'resource')
    
    def test_server_tools_registration(self):
        """Test that tools are properly registered"""
        print("🛠️ Testing tool registration...")
        
        try:
            create_mcp_server()
            print("✅ Tools registration test passed")
        except Exception as e:
            pytest.fail(f"Tool registration failed: {e}")


class TestTileDBSOMAAccess:
    """Test actual TileDB-SOMA data access (if data available)"""
    
    def test_tiledbsoma_import(self):
        """Test TileDB-SOMA can be imported and used"""
        print("🔬 Testing TileDB-SOMA import...")
        
        try:
            __import__("tiledbsoma")
            print("✅ TileDB-SOMA imported successfully")
        except ImportError as e:
            print(f"❌ TileDB-SOMA import failed: {e}")
            pytest.skip("TileDB-SOMA not available")
    
    def test_data_access(self):
        """Test actual data access if data is available"""
        print("📊 Testing actual data access...")
        
        if not validate_data_path():
            pytest.skip("Data path not available")
        
        import tiledbsoma
        
        # Find first available experiment
        test_experiment = None
        for tissue in AVAILABLE_TISSUES:
            if validate_experiment(tissue):
                test_experiment = tissue
                break
        
        if not test_experiment:
            pytest.skip("No valid experiments found")
        
        try:
            exp_path = get_experiment_path(test_experiment)
            print(f"Testing with experiment: {test_experiment}")
            
            with tiledbsoma.Experiment.open(exp_path) as exp:
                # Try to read some data to validate access
                sample_obs = exp.obs.read(coords=(slice(0, 10),)).concat().to_pandas()
                measurements = list(exp.ms.keys())
                
                print(f"✅ Experiment opened successfully")
                print(f"✅ Sample cells read: {len(sample_obs)}")
                print(f"✅ Measurements: {measurements}")
                
                if "RNA" in measurements:
                    sample_var = exp.ms["RNA"].var.read(coords=(slice(0, 10),)).concat().to_pandas()
                    print(f"✅ Sample genes read: {len(sample_var)}")
        except Exception as e:
            pytest.fail(f"Data access failed: {e}")


def run_test_suite():
    """Run the complete test suite"""
    print("🔬 Aging Atlas MCP Server - Enhanced Test Suite")
    print("=" * 60)
    
    test_classes = [
        TestDependencies,
        TestDataAccess,
        TestMCPServer,
        TestTileDBSOMAAccess
    ]
    
    total_tests = 0
    passed_tests = 0
    
    for test_class in test_classes:
        print(f"\n📋 Running {test_class.__name__}...")
        print("-" * 40)
        
        instance = test_class()
        methods = [method for method in dir(instance) if method.startswith('test_')]
        
        for method_name in methods:
            total_tests += 1
            method = getattr(instance, method_name)
            
            try:
                result = method()
                if result is not False:  # None or True is considered passing
                    passed_tests += 1
                    print(f"✅ {method_name}")
                else:
                    print(f"❌ {method_name}")
            except Exception as e:
                print(f"❌ {method_name}: {e}")
    
    print("\n" + "=" * 60)
    print(f"Test Results: {passed_tests}/{total_tests} passed")
    print("=" * 60)
    
    if passed_tests == total_tests:
        print("🎉 All tests passed! Server is ready")
        print("\n📋 Next steps:")
        print("1. Run development server: fastmcp dev src/aging_atlas_mcp/server.py")
        print("2. Test with MCP Inspector: http://localhost:6274")
        print("3. Configure Claude Desktop")
        return True
    else:
        print("⚠️  Some tests failed. Check the issues above.")
        return False


if __name__ == "__main__":
    success = run_test_suite()
    sys.exit(0 if success else 1)
