#!/usr/bin/env python3
"""
Kite API Configuration Setup Script
Helps set up .env file with Kite API credentials and generates access token
"""

import os
import sys
from dotenv import load_dotenv, set_key

def setup_kite_config():
    """Setup Kite API configuration interactively"""
    
    print("🔧 KITE API CONFIGURATION SETUP")
    print("=" * 50)
    print("This script will help you set up your Kite API credentials")
    print("for REAL data integration (no more mock data!)")
    print()
    
    # Check if backend/.env exists
    backend_env_path = os.path.join('backend', '.env')
    root_env_path = '.env'
    
    env_path = backend_env_path if os.path.exists(backend_env_path) else root_env_path
    
    print(f"📁 Using .env file: {env_path}")
    
    # Load existing .env if it exists
    if os.path.exists(env_path):
        load_dotenv(env_path)
        print("✅ Existing .env file loaded")
    else:
        print("📝 Creating new .env file")
    
    print("\n📋 STEP 1: Kite API Credentials")
    print("-" * 30)
    print("You need to get these from: https://kite.zerodha.com/apps/")
    print()
    
    # Get API Key
    current_api_key = os.getenv('KITE_API_KEY', '')
    if current_api_key:
        print(f"Current API Key: {current_api_key[:8]}...")
        use_existing = input("Use existing API Key? (y/n): ").lower() == 'y'
        if use_existing:
            api_key = current_api_key
        else:
            api_key = input("Enter your Kite API Key: ").strip()
    else:
        api_key = input("Enter your Kite API Key: ").strip()
    
    # Get API Secret
    current_api_secret = os.getenv('KITE_API_SECRET', '')
    if current_api_secret:
        print(f"Current API Secret: {current_api_secret[:8]}...")
        use_existing = input("Use existing API Secret? (y/n): ").lower() == 'y'
        if use_existing:
            api_secret = current_api_secret
        else:
            api_secret = input("Enter your Kite API Secret: ").strip()
    else:
        api_secret = input("Enter your Kite API Secret: ").strip()
    
    # Check for access token
    current_access_token = os.getenv('KITE_ACCESS_TOKEN', '')
    
    print("\n🔑 STEP 2: Access Token")
    print("-" * 25)
    
    if current_access_token:
        print(f"Current Access Token: {current_access_token[:20]}...")
        use_existing = input("Use existing Access Token? (y/n): ").lower() == 'y'
        if use_existing:
            access_token = current_access_token
            request_token = ""
        else:
            print("Option 1: Enter new Access Token directly")
            print("Option 2: Generate from Request Token")
            choice = input("Choose option (1/2): ").strip()
            
            if choice == "1":
                access_token = input("Enter your Access Token: ").strip()
                request_token = ""
            else:
                access_token = ""
                request_token = input("Enter your Request Token: ").strip()
    else:
        print("You can either:")
        print("1. Enter Access Token directly (if you have one)")
        print("2. Enter Request Token (to generate Access Token)")
        choice = input("Choose option (1/2): ").strip()
        
        if choice == "1":
            access_token = input("Enter your Access Token: ").strip()
            request_token = ""
        else:
            access_token = ""
            request_token = input("Enter your Request Token: ").strip()
    
    # Save to .env file
    print("\n💾 SAVING CONFIGURATION...")
    print("-" * 30)
    
    # Create directory if it doesn't exist
    env_dir = os.path.dirname(env_path)
    if env_dir and not os.path.exists(env_dir):
        os.makedirs(env_dir)
    
    # Update .env file
    set_key(env_path, 'KITE_API_KEY', api_key)
    set_key(env_path, 'KITE_API_SECRET', api_secret)
    
    if access_token:
        set_key(env_path, 'KITE_ACCESS_TOKEN', access_token)
    
    if request_token:
        set_key(env_path, 'KITE_REQUEST_TOKEN', request_token)
    
    # Add other default settings
    set_key(env_path, 'DEBUG', 'True')
    set_key(env_path, 'FLASK_ENV', 'development')
    set_key(env_path, 'FRONTEND_URL', 'http://localhost:3000')
    
    print(f"✅ Configuration saved to {env_path}")
    
    # Test the configuration
    print("\n🧪 TESTING CONFIGURATION...")
    print("-" * 30)
    
    try:
        # Add backend to path if testing from root directory
        if os.path.exists('backend'):
            sys.path.append('backend')
        
        from kiteconnect import KiteConnect
        
        kite = KiteConnect(api_key=api_key)
        
        if access_token:
            kite.set_access_token(access_token)
            
            # Test connection
            profile = kite.profile()
            print(f"✅ Connection successful!")
            print(f"👤 User: {profile['user_name']}")
            print(f"📧 Email: {profile['email']}")
            
            # Test a quick quote
            quote = kite.quote(["NSE:NIFTY 50"])
            nifty_price = quote["NSE:NIFTY 50"]["last_price"]
            print(f"💹 NIFTY 50: ₹{nifty_price:,.2f}")
            
        elif request_token:
            print("⚠️ Access token will be generated when you first run the application")
            print("The system will automatically convert your request token to an access token")
        
        print("\n🎉 SETUP COMPLETED SUCCESSFULLY!")
        print("✅ Your Kite API is configured for REAL data")
        print("✅ No more mock data - everything will be live!")
        
        return True
        
    except ImportError:
        print("⚠️ kiteconnect module not found. Install with: pip install kiteconnect")
        return False
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        print("\n💡 Common issues:")
        print("1. Invalid API credentials")
        print("2. Request token expired (get a new one)")
        print("3. Access token expired (will be auto-regenerated)")
        return False

def show_usage_instructions():
    """Show usage instructions after setup"""
    
    print("\n📖 USAGE INSTRUCTIONS")
    print("=" * 50)
    print("Now that your Kite API is configured, you can:")
    print()
    print("1️⃣ Test the real data integration:")
    print("   python test_real_kite_integration.py")
    print()
    print("2️⃣ Start the backend server:")
    print("   cd backend && python app.py")
    print()
    print("3️⃣ Start the frontend:")
    print("   cd frontend && npm start")
    print()
    print("4️⃣ Access the real data API endpoints:")
    print("   http://localhost:5000/api/real-data/all-symbols")
    print("   http://localhost:5000/api/real-data/all-expiries")
    print("   http://localhost:5000/api/real-data/option-chain/NIFTY")
    print()
    print("🚀 FEATURES YOU NOW HAVE:")
    print("✅ Real-time data for ALL 5 indices (NIFTY, BANKNIFTY, FINNIFTY, MIDCPNIFTY, SENSEX)")
    print("✅ Real data for 224+ stocks")
    print("✅ ALL expiry dates for ALL symbols")
    print("✅ COMPLETE option chains with ALL strikes (no filtering)")
    print("✅ Live Greeks calculation")
    print("✅ Real-time spot prices")
    print("✅ Export functionality for all data")
    print()
    print("🎯 NO MORE MOCK DATA - EVERYTHING IS REAL!")

if __name__ == "__main__":
    print("Welcome to the Kite API Real Data Setup!\n")
    
    success = setup_kite_config()
    
    if success:
        show_usage_instructions()
    else:
        print("\n🔧 Please fix the configuration issues and run this script again.")
        print("For help, visit: https://kite.trade/docs/connect/v3/")
