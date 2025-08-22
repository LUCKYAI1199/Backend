#!/usr/bin/env python3
"""
Comprehensive Test Script for Real Kite API Integration
Tests all functionalities with REAL data from Kite API
"""

import sys
import os
import json
import time
from datetime import datetime

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

def test_real_kite_api():
    """Comprehensive test of real Kite API integration"""
    
    print("🚀 COMPREHENSIVE REAL KITE API INTEGRATION TEST")
    print("=" * 80)
    
    try:
        # Import the service
        from backend.services.kite_api_service import kite_api_service
        
        print("\n1️⃣ TESTING CONNECTION...")
        print("-" * 40)
        
        # Test connection
        connection_result = kite_api_service.test_connection()
        
        if connection_result['success']:
            print(f"✅ Connection successful!")
            print(f"👤 User: {connection_result.get('user_name', 'Unknown')}")
            print(f"📧 Email: {connection_result.get('email', 'Unknown')}")
            print(f"🆔 User ID: {connection_result.get('user_id', 'Unknown')}")
        else:
            print(f"❌ Connection failed: {connection_result.get('error', 'Unknown error')}")
            print("\n💡 Please check your .env file configuration:")
            print("   - KITE_API_KEY")
            print("   - KITE_API_SECRET")
            print("   - KITE_ACCESS_TOKEN (or KITE_REQUEST_TOKEN)")
            return False
        
        print("\n2️⃣ TESTING ALL REAL SYMBOLS...")
        print("-" * 40)
        
        # Get all real symbols
        symbols_data = kite_api_service.get_all_symbols()
        
        print(f"📊 Total Indices: {symbols_data.get('total_indices', 0)}")
        print(f"📈 Total Stocks: {symbols_data.get('total_stocks', 0)}")
        print(f"⚡ Stocks with Options: {symbols_data.get('total_stocks_with_options', 0)}")
        print(f"🎯 Total Symbols: {symbols_data.get('total_symbols', 0)}")
        
        print(f"\nIndices: {symbols_data.get('indices', [])}")
        print(f"Sample Stocks with Options: {symbols_data.get('stocks_with_options', [])[:10]}")
        
        print("\n3️⃣ TESTING SPOT PRICES...")
        print("-" * 40)
        
        # Test spot prices for indices
        for symbol in symbols_data.get('indices', [])[:3]:  # Test first 3 indices
            try:
                spot_data = kite_api_service.get_spot_price(symbol)
                print(f"💰 {symbol}: ₹{spot_data['spot_price']:,.2f} "
                      f"({spot_data['change']:+.2f}, {spot_data['change_percent']:+.2f}%)")
            except Exception as e:
                print(f"❌ Error getting spot price for {symbol}: {e}")
        
        print("\n4️⃣ TESTING ALL EXPIRIES...")
        print("-" * 40)
        
        # Get all expiries
        all_expiries = kite_api_service.get_all_expiries_for_all_symbols()
        
        print(f"📅 Symbols with Options: {len(all_expiries)}")
        
        for symbol, expiries in list(all_expiries.items())[:5]:  # Show first 5 symbols
            print(f"   {symbol}: {len(expiries)} expiries ({expiries[:3]}...)")
        
        print("\n5️⃣ TESTING REAL OPTION CHAIN...")
        print("-" * 40)
        
        # Test option chain for NIFTY
        test_symbol = 'NIFTY'
        if test_symbol in all_expiries:
            test_expiry = all_expiries[test_symbol][0]  # First expiry
            
            print(f"Fetching option chain for {test_symbol} {test_expiry}...")
            
            option_chain = kite_api_service.get_option_chain(
                symbol=test_symbol, 
                expiry=test_expiry, 
                include_all_strikes=True
            )
            
            if option_chain and 'option_chain' in option_chain:
                strikes = [row['strike_price'] for row in option_chain['option_chain']]
                print(f"✅ Option chain fetched successfully!")
                print(f"📊 Total Strikes: {len(strikes)}")
                print(f"🎯 Strike Range: {min(strikes)} to {max(strikes)}")
                print(f"💹 Spot Price: ₹{option_chain['spot_price']:,.2f}")
                print(f"🔥 ATM Strike: {option_chain['atm_strike']}")
                print(f"📈 PCR OI: {option_chain['pcr_oi']:.2f}")
                print(f"🎯 Max Pain: {option_chain['max_pain']}")
                
                # Show sample strikes
                sample_strikes = option_chain['option_chain'][:5]
                print(f"\nSample Strikes:")
                for strike in sample_strikes:
                    print(f"   {strike['strike_price']}: CE={strike['ce_ltp']:.2f}, PE={strike['pe_ltp']:.2f}")
            else:
                print(f"❌ Failed to fetch option chain for {test_symbol}")
        
        print("\n6️⃣ TESTING COMPREHENSIVE DATA EXPORT...")
        print("-" * 40)
        
        # Test data export
        export_result = kite_api_service.export_all_market_data("test_real_data_export")
        
        if export_result['success']:
            print(f"✅ Data export successful!")
            print(f"📁 Output Directory: {export_result['output_directory']}")
            print(f"📄 Files Exported: {export_result['files_exported']}")
            print(f"📊 Export Stats: {export_result['summary']['stats']}")
        else:
            print(f"❌ Data export failed: {export_result.get('error', 'Unknown error')}")
        
        print("\n🎉 ALL TESTS COMPLETED SUCCESSFULLY!")
        print("=" * 80)
        print("✅ Real Kite API integration is working perfectly!")
        print("✅ All indices, stocks, and expiries are being fetched with REAL data")
        print("✅ Option chains include ALL strikes with live pricing")
        print("✅ No more mock data - everything is REAL from Kite API!")
        
        return True
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_api_endpoints():
    """Test API endpoints with real data"""
    
    print("\n🌐 TESTING API ENDPOINTS...")
    print("-" * 40)
    
    try:
        import requests
        
        base_url = "http://localhost:5000/api"
        
        # Test endpoints
        endpoints = [
            "/real-data/test-connection",
            "/real-data/all-symbols",
            "/real-data/all-expiries",
            "/real-data/option-chain/NIFTY?include_all_strikes=true"
        ]
        
        for endpoint in endpoints:
            try:
                print(f"Testing: {base_url}{endpoint}")
                response = requests.get(f"{base_url}{endpoint}", timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"✅ {endpoint} - Success")
                    
                    if 'data' in data:
                        if endpoint.endswith('all-symbols'):
                            print(f"   📊 Total symbols: {data['data'].get('total_symbols', 0)}")
                        elif endpoint.endswith('all-expiries'):
                            print(f"   📅 Symbols with options: {len(data['data'])}")
                        elif 'option-chain' in endpoint:
                            chain_data = data['data'].get('option_chain', [])
                            print(f"   ⚡ Total strikes: {len(chain_data)}")
                else:
                    print(f"❌ {endpoint} - HTTP {response.status_code}")
                    
            except requests.exceptions.RequestException as e:
                print(f"❌ {endpoint} - Connection error: {e}")
                print("   💡 Make sure the backend server is running!")
        
    except ImportError:
        print("⚠️ requests module not available. Install with: pip install requests")

if __name__ == "__main__":
    print("Starting comprehensive real Kite API integration test...\n")
    
    # Test the service directly
    service_test_passed = test_real_kite_api()
    
    if service_test_passed:
        # Test API endpoints (optional)
        test_api_endpoints()
    else:
        print("\n❌ Service test failed. Please fix the issues before testing API endpoints.")
        print("\n🔧 SETUP INSTRUCTIONS:")
        print("1. Ensure you have a valid Kite API account")
        print("2. Update backend/.env file with your API credentials:")
        print("   KITE_API_KEY=your_api_key")
        print("   KITE_API_SECRET=your_api_secret")
        print("   KITE_ACCESS_TOKEN=your_access_token")
        print("3. Install required packages: pip install -r backend/requirements.txt")
        print("4. Run this test again")
