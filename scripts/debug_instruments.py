#!/usr/bin/env python3
"""
Debug Kite API Instruments
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from backend.services.kite_api_service import kite_api_service
import pandas as pd

def debug_instruments():
    """Debug instruments structure"""
    print("🔍 Debugging Kite API Instruments...")
    print("=" * 50)
    
    try:
        # Get NFO instruments
        instruments_df = kite_api_service._get_instruments("NFO")
        
        print(f"Total instruments: {len(instruments_df)}")
        print(f"Columns: {list(instruments_df.columns)}")
        
        if not instruments_df.empty:
            print("\nFirst few rows:")
            print(instruments_df.head())
            
            # Check NIFTY instruments
            nifty_instruments = instruments_df[instruments_df['name'] == 'NIFTY']
            print(f"\nNIFTY instruments: {len(nifty_instruments)}")
            
            if not nifty_instruments.empty:
                print("NIFTY columns:")
                for col in nifty_instruments.columns:
                    sample_value = nifty_instruments[col].iloc[0]
                    print(f"  {col}: {type(sample_value)} = {sample_value}")
                
                # Check expiry column specifically
                if 'expiry' in nifty_instruments.columns:
                    print(f"\nExpiry column type: {type(nifty_instruments['expiry'].iloc[0])}")
                    print(f"Expiry sample values: {nifty_instruments['expiry'].head().tolist()}")
                
                # Show option types
                print(f"\nInstrument types: {nifty_instruments['instrument_type'].unique()}")
                
                # Filter options
                nifty_options = nifty_instruments[
                    nifty_instruments['instrument_type'].isin(['CE', 'PE'])
                ]
                print(f"NIFTY options: {len(nifty_options)}")
                
                if not nifty_options.empty and 'expiry' in nifty_options.columns:
                    # Try to get unique expiries
                    try:
                        expiries = nifty_options['expiry'].unique()
                        print(f"Unique expiries: {len(expiries)}")
                        print(f"Sample expiries: {expiries[:5]}")
                    except Exception as e:
                        print(f"Error getting expiries: {e}")
        
    except Exception as e:
        print(f"Error debugging instruments: {e}")

if __name__ == "__main__":
    debug_instruments()
