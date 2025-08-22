#!/usr/bin/env python3
"""
Debug script to check the actual API response structure
"""

import requests
import json
import sys

def debug_api_response():
    """Debug the API response to see the actual structure"""
    
    print("🔍 Debugging API Response Structure...")
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
        
        print(f"✅ Received response with status code: {response.status_code}")
        print(f"📋 Response keys: {list(data.keys())}")
        
        # Show the full structure (limited to avoid too much output)
        print(f"\n📄 Full Response Structure:")
        print(json.dumps(data, indent=2, default=str)[:2000] + "...")
        
        # Look for option data in different possible locations
        if 'option_chain' in data:
            print(f"\n✅ Found 'option_chain' key")
            option_chain = data['option_chain']
            if option_chain:
                print(f"   First strike data: {option_chain[0]}")
        
        if 'data' in data:
            print(f"\n✅ Found 'data' key")
            data_content = data['data']
            print(f"   Data type: {type(data_content)}")
            if isinstance(data_content, dict):
                print(f"   Data keys: {list(data_content.keys())}")
            elif isinstance(data_content, list) and data_content:
                print(f"   Data length: {len(data_content)}")
                print(f"   First item: {data_content[0]}")
        
        # Look for any array of strikes
        for key, value in data.items():
            if isinstance(value, list) and value:
                print(f"\n📊 Found array '{key}' with {len(value)} items")
                first_item = value[0]
                if isinstance(first_item, dict) and 'strike' in first_item:
                    print(f"   Looks like option data! First strike: {first_item.get('strike')}")
                    print(f"   Keys in first item: {list(first_item.keys())}")
                    
                    # Check for Greeks in CE/PE data
                    ce_data = first_item.get('ce', {})
                    pe_data = first_item.get('pe', {})
                    
                    if ce_data:
                        print(f"   CE keys: {list(ce_data.keys())}")
                        if 'ce_rho' in ce_data:
                            print(f"   ✅ CE RHO found: {ce_data['ce_rho']}")
                        else:
                            print(f"   ❌ CE RHO not found")
                    
                    if pe_data:
                        print(f"   PE keys: {list(pe_data.keys())}")
                        if 'pe_rho' in pe_data:
                            print(f"   ✅ PE RHO found: {pe_data['pe_rho']}")
                        else:
                            print(f"   ❌ PE RHO not found")
                    
                    break
        
        return True
            
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
    debug_api_response()
