import requests
import json

# Test the API endpoint directly
try:
    url = "http://localhost:5000/api/real-data/option-chain/NIFTY"
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        print("API Response Success!")
        
        if 'data' in data and 'option_chain' in data['data']:
            option_chain = data['data']['option_chain']
            print(f"Option chain has {len(option_chain)} rows")
            
            # Check first few rows for rho values
            for i, row in enumerate(option_chain[:3]):
                print(f"\nRow {i+1}: Strike {row.get('strike_price', 'N/A')}")
                print(f"  CE RHO: {row.get('ce_rho', 'MISSING')}")
                print(f"  PE RHO: {row.get('pe_rho', 'MISSING')}")
                print(f"  CE LTP: {row.get('ce_ltp', 'MISSING')}")
                print(f"  PE LTP: {row.get('pe_ltp', 'MISSING')}")
                print(f"  CE Gamma: {row.get('ce_gamma', 'MISSING')}")
                print(f"  PE Gamma: {row.get('pe_gamma', 'MISSING')}")
        else:
            print("No option chain data in response")
            print("Response keys:", list(data.keys()) if isinstance(data, dict) else "Not a dict")
    else:
        print(f"API Error: {response.status_code}")
        print(response.text)

except Exception as e:
    print(f"Error: {e}")
