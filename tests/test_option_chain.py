#!/usr/bin/env python3
"""
Test option chain functionality
"""

import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

try:
    from backend.services.kite_api_service import kite_api_service
    
    print("Testing option chain for NIFTY...")
    
    # Get expiries first
    expiries = kite_api_service.get_expiry_dates('NIFTY')
    print(f"Available expiries: {expiries[:5]}")
    
    if expiries:
        test_expiry = expiries[0]
        print(f"Testing option chain for NIFTY {test_expiry}...")
        
        option_chain = kite_api_service.get_option_chain('NIFTY', test_expiry, include_all_strikes=True)
        
        if option_chain and 'option_chain' in option_chain:
            strikes = [row['strike_price'] for row in option_chain['option_chain']]
            print(f"✅ Option chain fetched successfully!")
            print(f"📊 Total Strikes: {len(strikes)}")
            print(f"🎯 Strike Range: {min(strikes)} to {max(strikes)}")
            print(f"💹 Spot Price: ₹{option_chain['spot_price']:,.2f}")
            print(f"🔥 ATM Strike: {option_chain['atm_strike']}")
            
            # Show sample strikes
            sample_strikes = option_chain['option_chain'][:3]
            print(f"\nSample Strikes:")
            for strike in sample_strikes:
                print(f"   {strike['strike_price']}: CE={strike['ce_ltp']:.2f}, PE={strike['pe_ltp']:.2f}")
        else:
            print("❌ Failed to fetch option chain")
    else:
        print("❌ No expiries found")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
