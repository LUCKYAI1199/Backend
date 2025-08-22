#!/usr/bin/env python3
"""
🚀 QUICK ACCESS TOKEN GENERATOR
==============================
Generate access token from your request token: 95V9Emfu8VdsCCnY925nq859NYKzycld
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

try:
    from kiteconnect import KiteConnect
    print("✅ Kite Connect library available")
    
    # Your credentials
    API_KEY = "pisk12j49il1s9ly"
    API_SECRET = "fro42yzfifildkjg41fid4aikwcmb0kw"
    REQUEST_TOKEN = "mY5d8mGlfd528j9YOc9hWt125YctTOd6"
    
    print("🔑 GENERATING ACCESS TOKEN")
    print("=" * 40)
    print(f"API Key: {API_KEY}")
    print(f"Request Token: {REQUEST_TOKEN}")
    
    # Initialize Kite Connect
    kite = KiteConnect(api_key=API_KEY)
    
    # Generate access token
    data = kite.generate_session(
        request_token=REQUEST_TOKEN,
        api_secret=API_SECRET
    )
    
    access_token = data['access_token']
    user_id = data['user_id']
    
    print(f"\n✅ SUCCESS!")
    print(f"Access Token: {access_token}")
    print(f"User ID: {user_id}")
    
    # Test the token
    kite.set_access_token(access_token)
    profile = kite.profile()
    
    print(f"\n✅ AUTHENTICATION TEST:")
    print(f"User: {profile.get('user_name', 'N/A')}")
    print(f"Email: {profile.get('email', 'N/A')}")
    
    # Test NIFTY data
    quotes = kite.quote(["NSE:NIFTY 50"])
    nifty_data = quotes["NSE:NIFTY 50"]
    
    print(f"\n✅ LIVE NIFTY 50 DATA:")
    print(f"LTP: ₹{nifty_data['last_price']}")
    print(f"Change: {nifty_data['net_change']}")
    print(f"Volume: {nifty_data['volume']:,}")
    
    # Update .env file
    print(f"\n💾 UPDATING .ENV FILE...")
    
    # Read current .env content
    env_content = []
    with open('.env', 'r') as f:
        env_content = f.readlines()
    
    # Update access token
    updated = False
    for i, line in enumerate(env_content):
        if line.startswith('KITE_ACCESS_TOKEN='):
            env_content[i] = f'KITE_ACCESS_TOKEN={access_token}\n'
            updated = True
            break
    
    if not updated:
        env_content.append(f'KITE_ACCESS_TOKEN={access_token}\n')
    
    # Write back
    with open('.env', 'w') as f:
        f.writelines(env_content)
    
    print(f"✅ .env file updated successfully!")
    
    print(f"\n🎯 KITE CONNECT SETUP COMPLETE!")
    print(f"✅ Kite Connect is now your PRIMARY data source")
    print(f"✅ NSE Python configured as SECONDARY fallback")
    print(f"✅ Start your server: python kite_priority_live_server.py")
    
except Exception as e:
    print(f"❌ Error: {e}")
    print(f"\n💡 Troubleshooting:")
    print("1. Make sure your request token is fresh (not expired)")
    print("2. Verify API key and secret are correct")
    print("3. Check internet connection")
    print("4. Get new request token from:")
    print("   https://kite.zerodha.com/connect/login?api_key=pisk12j49il1s9ly&v=3")
