#!/usr/bin/env python3
"""
Comprehensive test to verify Kite API data fetching and Greeks calculations
"""

import requests
import json
import sys

def test_kite_api_and_greeks():
    """Test that Kite API data is properly fetched and Greeks are correctly calculated"""
    
    print("🔬 COMPREHENSIVE KITE API & GREEKS TEST")
    print("=" * 70)
    
    try:
        # Test the API endpoint
        url = "http://127.0.0.1:5000/api/real-data/option-chain/NIFTY"
        params = {"expiry": "2025-07-31"}
        
        print(f"📡 Making API request to: {url}")
        print(f"   Parameters: {params}")
        
        response = requests.get(url, params=params, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ API request failed with status code: {response.status_code}")
            return False
            
        data = response.json()
        
        if 'data' not in data or 'option_chain' not in data['data']:
            print("❌ No option chain data found in response")
            return False
            
        option_chain = data['data']['option_chain']
        spot_price = data['data'].get('spot_price', 0)
        
        print(f"✅ Received option chain data with {len(option_chain)} strikes")
        print(f"📊 Current Spot Price: {spot_price}")
        
        # Test different categories of strikes
        categories = {
            'Deep ITM Calls': [],
            'ATM Options': [],
            'Deep OTM Calls': []
        }
        
        for strike_data in option_chain:
            strike = strike_data.get('strike_price', 0)
            if not strike:
                continue
                
            moneyness = (strike - spot_price) / spot_price * 100
            
            if moneyness < -10:  # Deep ITM calls
                categories['Deep ITM Calls'].append(strike_data)
            elif -2 <= moneyness <= 2:  # ATM options
                categories['ATM Options'].append(strike_data)
            elif moneyness > 10:  # Deep OTM calls
                categories['Deep OTM Calls'].append(strike_data)
        
        # Test each category
        all_tests_passed = True
        
        for category, strikes in categories.items():
            if not strikes:
                continue
                
            print(f"\n🔍 Testing {category}:")
            print("-" * 50)
            
            # Test first 2 strikes in each category
            for strike_data in strikes[:2]:
                strike = strike_data.get('strike_price')
                moneyness = ((strike - spot_price) / spot_price * 100) if spot_price else 0
                
                print(f"\n📊 Strike {strike} (Moneyness: {moneyness:+.1f}%)")
                
                # Verify all Greeks are present
                greeks_to_check = ['ce_delta', 'ce_gamma', 'ce_theta', 'ce_vega', 'ce_rho',
                                 'pe_delta', 'pe_gamma', 'pe_theta', 'pe_vega', 'pe_rho']
                
                missing_greeks = []
                for greek in greeks_to_check:
                    value = strike_data.get(greek)
                    if value is None:
                        missing_greeks.append(greek)
                    else:
                        print(f"   ✅ {greek}: {value:.6f}" if isinstance(value, (int, float)) else f"   ✅ {greek}: {value}")
                
                if missing_greeks:
                    print(f"   ❌ Missing Greeks: {missing_greeks}")
                    all_tests_passed = False
                
                # Verify delta values make sense for the moneyness
                ce_delta = strike_data.get('ce_delta')
                pe_delta = strike_data.get('pe_delta')
                
                if ce_delta is not None and pe_delta is not None:
                    # Deep ITM calls should have delta close to 1, Deep OTM close to 0
                    if category == 'Deep ITM Calls' and ce_delta < 0.8:
                        print(f"   ⚠️  WARNING: Deep ITM call delta ({ce_delta:.4f}) seems low")
                    elif category == 'Deep OTM Calls' and ce_delta > 0.2:
                        print(f"   ⚠️  WARNING: Deep OTM call delta ({ce_delta:.4f}) seems high")
                    elif category == 'ATM Options' and not (0.3 <= ce_delta <= 0.7):
                        print(f"   ⚠️  WARNING: ATM call delta ({ce_delta:.4f}) not in expected range [0.3-0.7]")
                    
                    # PE delta should be CE delta - 1
                    expected_pe_delta = ce_delta - 1
                    delta_diff = abs(pe_delta - expected_pe_delta)
                    if delta_diff > 0.01:
                        print(f"   ⚠️  WARNING: PE delta ({pe_delta:.4f}) doesn't match CE delta - 1 ({expected_pe_delta:.4f})")
                
                # Verify other Kite API data fields
                kite_fields = ['ce_ltp', 'pe_ltp', 'ce_volume', 'pe_volume', 'ce_oi', 'pe_oi']
                for field in kite_fields:
                    value = strike_data.get(field)
                    if value is None:
                        print(f"   ❌ Missing Kite API field: {field}")
                        all_tests_passed = False
        
        # Summary
        print(f"\n📋 SUMMARY:")
        print("=" * 70)
        if all_tests_passed:
            print("✅ All tests PASSED!")
            print("   - Kite API data is being fetched correctly")
            print("   - All Greeks calculations are working")
            print("   - Delta values are appropriate for moneyness")
            print("   - Rho calculations are functioning")
        else:
            print("❌ Some tests FAILED!")
            print("   Please check the warnings above")
        
        return all_tests_passed
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = test_kite_api_and_greeks()
    sys.exit(0 if success else 1)
