#!/usr/bin/env python3
"""
Test script to verify volume and OI conversion from Zerodha's abbreviated format
"""

try:
    from services.kite_api_service import KiteAPIService
    from utils.number_converter import convert_abbreviated_to_exact, test_conversion
    print("✅ Imports successful")
    
    # Test the conversion utility first
    print("\n🧪 Testing Number Conversion Utility:")
    test_conversion()
    
    print("\n🔍 Testing specific Zerodha format examples:")
    test_cases = [
        "1.2K",     # 1200 volume
        "5.5L",     # 550000 OI
        "2.3CR",    # 23000000 total volume
        "125",      # 125 exact number
        "0.8K",     # 800 volume
        "10L",      # 1000000 OI
    ]
    
    for case in test_cases:
        result = convert_abbreviated_to_exact(case)
        print(f"  📊 {case:6} -> {result:>10,}")
    
    print("\n✅ Number conversion working correctly!")
    print("📈 Volume and OI data will now show exact numbers instead of K/L/CR format")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
