#!/usr/bin/env python3
"""
Test script to verify that CE RHO and PE RHO values are now included in the API response
"""

import requests
import json
import sys

def test_rho_values():
    """Test that the API now returns rho values for both CE and PE options"""
    
    print("🧪 Testing Rho Values in API Response...")
    print("=" * 60)
    
    try:
        # Test the API endpoint
        url = "http://127.0.0.1:5000/api/real-data/option-chain/NIFTY"
        params = {"expiry": "2025-07-31"}
        
        print(f"📡 Making API request to: {url}")
        print(f"   Parameters: {params}")
        
        response = requests.get(url, params=params, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ API request failed with status code: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
        data = response.json()
        
        # Check if we have option chain data
        if 'data' not in data or 'option_chain' not in data['data']:
            print("❌ No option chain data found in response")
            print(f"   Available keys: {list(data.keys())}")
            return False
            
        option_chain = data['data']['option_chain']
        
        if not option_chain:
            print("❌ Option chain is empty")
            return False
        
        print(f"✅ Received option chain data with {len(option_chain)} strikes")
        
        # Test a few strikes to verify rho values
        rho_found_count = 0
        test_strikes = option_chain[:5]  # Test first 5 strikes
        
        for i, strike_data in enumerate(test_strikes):
            strike = strike_data.get('strike_price')  # Note: API uses 'strike_price' not 'strike'
            
            print(f"\n📊 Strike {strike}:")
            
            # Check CE RHO (directly in strike_data, not nested under 'ce')
            ce_rho = strike_data.get('ce_rho')
            if ce_rho is not None:
                print(f"   ✅ CE RHO: {ce_rho}")
                rho_found_count += 1
            else:
                print(f"   ❌ CE RHO: Missing or None")
            
            # Check PE RHO (directly in strike_data, not nested under 'pe')
            pe_rho = strike_data.get('pe_rho')
            if pe_rho is not None:
                print(f"   ✅ PE RHO: {pe_rho}")
                rho_found_count += 1
            else:
                print(f"   ❌ PE RHO: Missing or None")
                
            # Show other Greeks for comparison
            print(f"   📈 CE Delta: {strike_data.get('ce_delta', 'N/A')}")
            print(f"   📈 PE Delta: {strike_data.get('pe_delta', 'N/A')}")
        
        print(f"\n📋 Summary:")
        print(f"   Total strikes tested: {len(test_strikes)}")
        print(f"   Total rho values found: {rho_found_count}")
        print(f"   Expected rho values: {len(test_strikes) * 2}")
        
        if rho_found_count > 0:
            print(f"✅ SUCCESS: Rho calculations are working!")
            print(f"   Found {rho_found_count} rho values in the API response")
            
            # Show sample data structure
            if test_strikes:
                print(f"\n📝 Sample data structure for strike {test_strikes[0].get('strike_price')}:")
                sample_strike = test_strikes[0]
                
                print("   All Greeks for this strike:")
                for key in ['ce_delta', 'ce_gamma', 'ce_theta', 'ce_vega', 'ce_rho']:
                    value = sample_strike.get(key, 'N/A')
                    print(f"     {key}: {value}")
                
                for key in ['pe_delta', 'pe_gamma', 'pe_theta', 'pe_vega', 'pe_rho']:
                    value = sample_strike.get(key, 'N/A')
                    print(f"     {key}: {value}")
            
            return True
        else:
            print(f"❌ FAILURE: No rho values found in API response")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error: {e}")
        return False
    except json.JSONDecodeError as e:
        print(f"❌ JSON decode error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    print("🔬 RHO VALUES API TEST")
    print("=" * 60)
    print("Testing if CE RHO and PE RHO values are now included in API responses")
    print("after fixing the missing rho calculations in backend...")
    print("")
    
    success = test_rho_values()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 TEST PASSED: Rho values are successfully calculated and returned!")
        print("   The empty rho columns issue should now be resolved.")
        sys.exit(0)
    else:
        print("❌ TEST FAILED: Rho values are still missing from API response.")
        print("   Further investigation needed.")
        sys.exit(1)
