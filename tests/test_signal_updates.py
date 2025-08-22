#!/usr/bin/env python3
"""
Test script for signal quality and confidence updates
"""

try:
    from services.kite_api_service import KiteAPIService
    print("✅ KiteAPIService imported successfully")
    
    # Create service instance
    service = KiteAPIService()
    print("✅ Service instance created")
    
    # Test the analysis fields calculation
    result = service._calculate_analysis_fields(
        option_type='CE',
        ltp=50.5,
        spot_price=24500,
        strike=24500,
        delta=0.6,
        gamma=0.008,
        theta=-0.03,
        vega=0.08,
        time_to_expiry=0.05
    )
    
    print("✅ Analysis fields calculated successfully")
    print("\n📊 Signal Analysis Results:")
    print(f"  signal_type: {result['signal_type']}")
    print(f"  signal_strength: {result['signal_strength']}")
    print(f"  signal_quality: {result['signal_quality']}")
    print(f"  signal_confidence: {result['signal_confidence']}")
    
    print("\n🔍 All analysis fields:")
    for key, value in result.items():
        print(f"  {key}: {value}")
    
    # Test with different parameters for low quality signal
    result2 = service._calculate_analysis_fields(
        option_type='PE',
        ltp=5.5,
        spot_price=24500,
        strike=25000,
        delta=-0.2,
        gamma=0.001,
        theta=-0.08,
        vega=0.02,
        time_to_expiry=0.02
    )
    
    print("\n📊 Low Quality Signal Test:")
    print(f"  signal_type: {result2['signal_type']}")
    print(f"  signal_strength: {result2['signal_strength']}")
    print(f"  signal_quality: {result2['signal_quality']}")
    print(f"  signal_confidence: {result2['signal_confidence']}")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
