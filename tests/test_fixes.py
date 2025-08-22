#!/usr/bin/env python3
"""
Quick test for the fixes
"""

import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

try:
    from backend.services.kite_api_service import kite_api_service
    
    print("Testing expiries fix...")
    expiries = kite_api_service.get_all_expiries_for_all_symbols()
    print(f"✅ Found expiries for {len(expiries)} symbols")
    
    if expiries:
        # Show sample
        sample_symbol = list(expiries.keys())[0]
        print(f"Sample: {sample_symbol} has {len(expiries[sample_symbol])} expiries")
    
    print("\nTesting export fix...")
    result = kite_api_service.export_all_market_data('test_export_quick')
    print(f"Export result: {'✅ Success' if result['success'] else '❌ Failed'}")
    
    if result['success']:
        print(f"📁 Files exported: {result['files_exported']}")
        print(f"📊 Stats: {result['summary']['stats']}")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
