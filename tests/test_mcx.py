#!/usr/bin/env python3
"""
Test script to check MCX commodity data fetching
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.kite_api_service import KiteAPIService
from config.settings import Config
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_mcx_commodities():
    """Test MCX commodity data fetching"""
    try:
        # Initialize Kite service
        kite_service = KiteAPIService()
        
        # Test MCX commodities
        mcx_commodities = ['COPPER', 'GOLD', 'SILVER', 'CRUDE OIL']
        
        for commodity in mcx_commodities:
            print(f"\n{'='*50}")
            print(f"Testing {commodity}")
            print(f"{'='*50}")
            
            try:
                # Test spot price
                spot_data = kite_service.get_spot_price(commodity)
                print(f"Spot Price: {spot_data}")
                
                # Test expiries
                expiries = kite_service.get_expiry_dates(commodity)
                print(f"Expiries: {expiries[:5] if expiries else 'None'}")  # Show first 5
                
                # Test option chain (if expiries exist)
                if expiries:
                    option_chain = kite_service.get_option_chain(commodity, expiries[0])
                    print(f"Option Chain: {len(option_chain.get('option_chain', []))} strikes")
                else:
                    print("No expiries found - MCX commodities might not have options")
                    
            except Exception as e:
                print(f"Error testing {commodity}: {e}")
                
    except Exception as e:
        print(f"Failed to initialize Kite service: {e}")
        print("Please check your Kite API configuration")

if __name__ == "__main__":
    test_mcx_commodities()
