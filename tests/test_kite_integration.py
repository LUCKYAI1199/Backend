#!/usr/bin/env python3
"""
Test Kite API Integration
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from backend.services.kite_api_service import kite_api_service
from backend.config.settings import Config

def test_kite_connection():
    """Test Kite API connection"""
    print("🔗 Testing Kite API Connection...")
    print("=" * 50)
    
    try:
        # Test connection
        connection_result = kite_api_service.test_connection()
        
        if connection_result['success']:
            print(f"✅ Connection successful!")
            print(f"   User: {connection_result['user_name']}")
            print(f"   Email: {connection_result['email']}")
            print(f"   User ID: {connection_result['user_id']}")
        else:
            print(f"❌ Connection failed: {connection_result['error']}")
            return False
            
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False
    
    return True

def test_symbols():
    """Test symbols fetching"""
    print("\n📊 Testing Symbols Fetching...")
    print("=" * 50)
    
    try:
        symbols = kite_api_service.get_all_symbols()
        print(f"✅ Indices ({len(symbols['indices'])}): {symbols['indices']}")
        print(f"✅ Stocks ({len(symbols['stocks'])}): {symbols['stocks'][:10]}...")  # First 10
        print(f"✅ Total symbols: {len(symbols['all'])}")
        
    except Exception as e:
        print(f"❌ Symbols test failed: {e}")
        return False
    
    return True

def test_spot_prices():
    """Test spot price fetching"""
    print("\n💰 Testing Spot Prices...")
    print("=" * 50)
    
    test_symbols = ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'SENSEX']
    
    for symbol in test_symbols:
        try:
            spot_data = kite_api_service.get_spot_price(symbol)
            print(f"✅ {symbol}: ₹{spot_data['spot_price']:,.2f} ({spot_data['change']:+.2f}, {spot_data['change_percent']:+.2f}%)")
            
        except Exception as e:
            print(f"❌ {symbol}: Error - {e}")

def test_expiries():
    """Test expiry dates fetching"""
    print("\n📅 Testing Expiry Dates...")
    print("=" * 50)
    
    test_symbols = ['NIFTY', 'BANKNIFTY']
    
    for symbol in test_symbols:
        try:
            expiries = kite_api_service.get_expiry_dates(symbol)
            print(f"✅ {symbol}: {len(expiries)} expiries")
            print(f"   Next 5: {expiries[:5]}")
            
        except Exception as e:
            print(f"❌ {symbol}: Error - {e}")

def test_option_chain():
    """Test option chain fetching"""
    print("\n⛓️  Testing Option Chain...")
    print("=" * 50)
    
    try:
        # Test NIFTY option chain
        print("Fetching NIFTY option chain (this may take a moment)...")
        option_data = kite_api_service.get_option_chain('NIFTY', strike_range=10)
        
        print(f"✅ NIFTY Option Chain:")
        print(f"   Spot Price: ₹{option_data['spot_price']:,.2f}")
        print(f"   Expiry: {option_data['expiry']}")
        print(f"   ATM Strike: {option_data['atm_strike']}")
        print(f"   Total CE OI: {option_data['total_ce_oi']:,}")
        print(f"   Total PE OI: {option_data['total_pe_oi']:,}")
        print(f"   PCR: {option_data['pcr_oi']:.2f}")
        print(f"   Strikes: {len(option_data['option_chain'])}")
        print(f"   Data Source: {option_data['data_source']}")
        
        # Show first few strikes
        print("\n   Sample Strikes:")
        for i, row in enumerate(option_data['option_chain'][:3]):
            strike = row['strike_price']
            ce_ltp = row['ce_ltp']
            pe_ltp = row['pe_ltp']
            print(f"   {strike}: CE {ce_ltp:.2f} | PE {pe_ltp:.2f}")
        
    except Exception as e:
        print(f"❌ Option chain test failed: {e}")
        return False
    
    return True

def main():
    """Main test function"""
    print("🚀 KITE API INTEGRATION TEST")
    print("=" * 60)
    
    # Check configuration
    print(f"API Key: {Config.KITE_API_KEY[:10]}..." if Config.KITE_API_KEY else "❌ No API Key")
    print(f"Access Token: {Config.KITE_ACCESS_TOKEN[:10]}..." if Config.KITE_ACCESS_TOKEN else "❌ No Access Token")
    
    if not Config.KITE_API_KEY or not Config.KITE_ACCESS_TOKEN:
        print("\n❌ Missing Kite API credentials in .env file")
        print("Please ensure KITE_API_KEY and KITE_ACCESS_TOKEN are set")
        return
    
    # Run tests
    tests = [
        ("Connection", test_kite_connection),
        ("Symbols", test_symbols),
        ("Spot Prices", test_spot_prices),
        ("Expiries", test_expiries),
        ("Option Chain", test_option_chain)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
    
    print(f"\n🎯 TEST RESULTS: {passed}/{total} tests passed")
    
    if passed == total:
        print("✅ All tests passed! Kite API integration is working correctly.")
        print("\n🚀 Ready to start the backend server:")
        print("   python app.py")
    else:
        print(f"❌ {total - passed} tests failed. Please check configuration and credentials.")

if __name__ == "__main__":
    main()
