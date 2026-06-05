#!/usr/bin/env python3
"""
Test script for TileDB-SOMA API calls
"""

import tiledbsoma
import pandas as pd

# Test path (override via SOMA_BASE_PATH env var)
import os
soma_path = os.path.join(os.getenv("SOMA_BASE_PATH", "./soma_data"), "Brain_experiment")

try:
    print("Testing TileDB-SOMA API...")
    
    with tiledbsoma.Experiment.open(soma_path) as exp:
        print("✓ Experiment opened successfully")
        
        # Test basic obs reading
        print("\n1. Testing basic obs reading...")
        obs_data = exp.obs.read(coords=(slice(0, 5),)).concat().to_pandas()
        print(f"   Shape: {obs_data.shape}")
        print(f"   Columns: {list(obs_data.columns)}")
        
        # Check if Main_cell_type exists
        if 'Main_cell_type' in obs_data.columns:
            print(f"   Cell types found: {obs_data['Main_cell_type'].unique()[:5]}")
        else:
            print("   Main_cell_type column not found")
            print(f"   Available columns: {list(obs_data.columns)}")
        
        # Test AxisQuery import
        print("\n2. Testing AxisQuery import...")
        try:
            from tiledbsoma import AxisQuery
            print("✓ tiledbsoma.AxisQuery imported successfully")
        except ImportError:
            try:
                import somacore
                AxisQuery = somacore.AxisQuery
                print("✓ somacore.AxisQuery imported successfully")
            except ImportError as e:
                print(f"✗ Failed to import AxisQuery: {e}")
                AxisQuery = None
        
        # Test axis_query if AxisQuery is available
        if AxisQuery:
            print("\n3. Testing axis_query...")
            try:
                # Simple query without filters first
                query = exp.axis_query("RNA")
                result = query.obs().concat().to_pandas()
                print(f"   Query result shape: {result.shape}")
                print("✓ Basic axis_query works")
                
                # Test with cell type filter if column exists
                if 'Main_cell_type' in result.columns:
                    unique_types = result['Main_cell_type'].dropna().unique()
                    if len(unique_types) > 0:
                        test_cell_type = unique_types[0]
                        print(f"\n4. Testing cell type filter with: {test_cell_type}")
                        
                        obs_query = AxisQuery(value_filter=f"Main_cell_type == '{test_cell_type}'")
                        filtered_query = exp.axis_query("RNA", obs_query=obs_query)
                        filtered_result = filtered_query.obs().concat().to_pandas()
                        print(f"   Filtered result shape: {filtered_result.shape}")
                        print("✓ Cell type filtering works")
                        
                        # Test to_anndata conversion
                        print("\n5. Testing to_anndata conversion...")
                        adata = filtered_query.to_anndata(X_name="data")  # Specify X_name
                        print(f"   AnnData shape: {adata.shape}")
                        print("✓ AnnData conversion works")
                    else:
                        print("   No cell types found for filtering test")
                else:
                    print("   Main_cell_type not available for filtering test")
                    
            except Exception as e:
                print(f"✗ axis_query failed: {e}")
        
        print("\n✓ All tests completed successfully!")
        
except Exception as e:
    print(f"✗ Test failed: {e}")
    import traceback
    traceback.print_exc()
