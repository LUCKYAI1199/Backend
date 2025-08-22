#!/usr/bin/env python3
"""
Simple test for MCX commodity symbols
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_mcx_symbols():
    """Test MCX symbol lookup without full Kite API"""
    print("Testing MCX symbol mapping...")
    
    # Test the trading symbol mapping logic
    mcx_commodities = ['COPPER', 'GOLD', 'SILVER', 'CRUDEOIL']
    
    for commodity in mcx_commodities:
        print(f"{commodity} -> MCX:{commodity} (futures lookup needed)")
    
    print("\nNote: Actual MCX symbols need to be retrieved from Kite instruments API")
    print("Example: COPPER might map to MCX:COPPER24DECFUT or similar")

if __name__ == "__main__":
    test_mcx_symbols()
