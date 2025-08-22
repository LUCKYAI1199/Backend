#!/usr/bin/env python3
"""
Complete Kite API Integration for Real Option Chain Data
Fetches all indices, stocks, and expiries using Kite Connect API
"""

import os
import pandas as pd
from dotenv import load_dotenv
from kiteconnect import KiteConnect
import logging
from datetime import datetime, timedelta
import time
import json
from typing import Dict, List, Optional, Tuple
import asyncio
import concurrent.futures
from dataclasses import dataclass

# Load environment variables
load_dotenv()

@dataclass
class MarketData:
    """Data class for market information"""
    symbol: str
    exchange: str
    instrument_token: int
    lot_size: int
    tick_size: float
    expiry: Optional[str] = None
    strike: Optional[float] = None
    instrument_type: Optional[str] = None

class ComprehensiveKiteAPI:
    """Complete Kite API integration for real option chain data"""
    
    def __init__(self):
        """Initialize the Kite API connection"""
        self.api_key = os.getenv('KITE_API_KEY')
        self.api_secret = os.getenv('KITE_API_SECRET')
        self.request_token = os.getenv('KITE_REQUEST_TOKEN')
        self.access_token = os.getenv('KITE_ACCESS_TOKEN')
        
        if not all([self.api_key, self.api_secret]):
            raise ValueError("KITE_API_KEY and KITE_API_SECRET must be set in .env file")
        
        # Initialize KiteConnect
        self.kite = KiteConnect(api_key=self.api_key)
        
        # Set access token if available
        if self.access_token:
            self.kite.set_access_token(self.access_token)
        elif self.request_token:
            self._generate_access_token()
        else:
            raise ValueError("Either KITE_ACCESS_TOKEN or KITE_REQUEST_TOKEN must be set")
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Market configuration
        self.indices = {
            'NIFTY': 'NSE:NIFTY 50',
            'BANKNIFTY': 'NSE:NIFTY BANK',
            'FINNIFTY': 'NSE:NIFTY FIN SERVICE',
            'MIDCPNIFTY': 'NSE:NIFTY MID SELECT',
            'SENSEX': 'BSE:SENSEX'
        }
        
        # Cache for instruments and data
        self.instruments_cache = {}
        self.option_chains_cache = {}
        self.last_cache_update = {}
        
        self.logger.info("Comprehensive Kite API initialized successfully")
    
    def _generate_access_token(self):
        """Generate access token from request token"""
        try:
            data = self.kite.generate_session(self.request_token, api_secret=self.api_secret)
            self.access_token = data["access_token"]
            self.kite.set_access_token(self.access_token)
            
            # Update .env file with new access token
            self._update_env_file('KITE_ACCESS_TOKEN', self.access_token)
            
            self.logger.info("Access token generated and saved successfully")
        except Exception as e:
            self.logger.error(f"Error generating access token: {e}")
            raise
    
    def _update_env_file(self, key: str, value: str):
        """Update .env file with new key-value pair"""
        try:
            env_path = '.env'
            lines = []
            
            # Read existing content
            if os.path.exists(env_path):
                with open(env_path, 'r') as f:
                    lines = f.readlines()
            
            # Update or add the key
            updated = False
            for i, line in enumerate(lines):
                if line.startswith(f'{key}='):
                    lines[i] = f'{key}={value}\n'
                    updated = True
                    break
            
            if not updated:
                lines.append(f'{key}={value}\n')
            
            # Write back
            with open(env_path, 'w') as f:
                f.writelines(lines)
                
        except Exception as e:
            self.logger.error(f"Error updating .env file: {e}")
    
    def get_all_instruments(self, force_refresh: bool = False) -> Dict[str, pd.DataFrame]:
        """Get all instruments from all exchanges"""
        cache_key = 'all_instruments'
        
        # Check cache
        if not force_refresh and cache_key in self.instruments_cache:
            cache_time = self.last_cache_update.get(cache_key, datetime.min)
            if datetime.now() - cache_time < timedelta(hours=1):
                return self.instruments_cache[cache_key]
        
        try:
            instruments_data = {}
            
            # Get instruments from each exchange
            exchanges = ['NSE', 'BSE', 'NFO', 'BFO', 'CDS', 'MCX']
            
            for exchange in exchanges:
                try:
                    self.logger.info(f"Fetching instruments from {exchange}...")
                    instruments = self.kite.instruments(exchange)
                    df = pd.DataFrame(instruments)
                    
                    if not df.empty and 'expiry' in df.columns:
                        df['expiry'] = pd.to_datetime(df['expiry'], errors='coerce')
                    
                    instruments_data[exchange] = df
                    self.logger.info(f"Fetched {len(df)} instruments from {exchange}")
                    
                    # Small delay to avoid rate limits
                    time.sleep(0.1)
                    
                except Exception as e:
                    self.logger.error(f"Error fetching instruments from {exchange}: {e}")
                    instruments_data[exchange] = pd.DataFrame()
            
            # Cache the results
            self.instruments_cache[cache_key] = instruments_data
            self.last_cache_update[cache_key] = datetime.now()
            
            return instruments_data
            
        except Exception as e:
            self.logger.error(f"Error fetching all instruments: {e}")
            return {}
    
    def get_all_indices_data(self) -> Dict[str, Dict]:
        """Get real-time data for all indices"""
        try:
            self.logger.info("Fetching real-time data for all indices...")
            
            # Get quotes for all indices
            index_symbols = list(self.indices.values())
            quotes = self.kite.quote(index_symbols)
            
            indices_data = {}
            for symbol, kite_symbol in self.indices.items():
                if kite_symbol in quotes:
                    quote_data = quotes[kite_symbol]
                    indices_data[symbol] = {
                        'symbol': symbol,
                        'kite_symbol': kite_symbol,
                        'last_price': quote_data['last_price'],
                        'change': quote_data['net_change'],
                        'change_percent': quote_data['net_change'] / quote_data['ohlc']['close'] * 100 if quote_data['ohlc']['close'] else 0,
                        'volume': quote_data['volume'],
                        'ohlc': quote_data['ohlc'],
                        'timestamp': quote_data['timestamp'],
                        'instrument_token': quote_data['instrument_token']
                    }
            
            self.logger.info(f"Fetched data for {len(indices_data)} indices")
            return indices_data
            
        except Exception as e:
            self.logger.error(f"Error fetching indices data: {e}")
            return {}
    
    def get_all_stocks_list(self) -> List[Dict]:
        """Get list of all 224+ tradeable stocks"""
        try:
            instruments_data = self.get_all_instruments()
            
            if 'NSE' not in instruments_data:
                return []
            
            nse_instruments = instruments_data['NSE']
            
            # Filter for equity stocks
            stocks = nse_instruments[
                (nse_instruments['instrument_type'] == 'EQ') &
                (nse_instruments['segment'] == 'NSE')
            ].copy()
            
            # Create stock list
            stock_list = []
            for _, stock in stocks.iterrows():
                stock_list.append({
                    'symbol': stock['tradingsymbol'],
                    'name': stock['name'],
                    'instrument_token': stock['instrument_token'],
                    'lot_size': stock['lot_size'],
                    'tick_size': stock['tick_size'],
                    'exchange': 'NSE'
                })
            
            # Sort by symbol for easy access
            stock_list = sorted(stock_list, key=lambda x: x['symbol'])
            
            self.logger.info(f"Found {len(stock_list)} tradeable stocks")
            return stock_list
            
        except Exception as e:
            self.logger.error(f"Error fetching stocks list: {e}")
            return []
    
    def get_all_expiries_for_symbol(self, symbol: str) -> List[str]:
        """Get all available expiry dates for a symbol"""
        try:
            instruments_data = self.get_all_instruments()
            
            # Determine exchange based on symbol
            if symbol == 'SENSEX':
                exchange = 'BFO'
            else:
                exchange = 'NFO'
            
            if exchange not in instruments_data:
                return []
            
            exchange_instruments = instruments_data[exchange]
            
            # Filter for the specific symbol's options
            symbol_options = exchange_instruments[
                (exchange_instruments['name'] == symbol) &
                (exchange_instruments['instrument_type'].isin(['CE', 'PE']))
            ].copy()
            
            if symbol_options.empty:
                return []
            
            # Get unique expiry dates
            expiries = symbol_options['expiry'].dropna().unique()
            expiries = sorted([exp.strftime('%Y-%m-%d') for exp in expiries if pd.notna(exp)])
            
            self.logger.info(f"Found {len(expiries)} expiry dates for {symbol}")
            return expiries
            
        except Exception as e:
            self.logger.error(f"Error fetching expiries for {symbol}: {e}")
            return []
    
    def get_complete_option_chain(self, symbol: str, expiry_date: Optional[str] = None, 
                                include_all_strikes: bool = True) -> pd.DataFrame:
        """Get complete option chain with ALL strikes for a symbol"""
        try:
            cache_key = f"{symbol}_{expiry_date}_{include_all_strikes}"
            
            # Check cache (refresh every 5 minutes for option data)
            if cache_key in self.option_chains_cache:
                cache_time = self.last_cache_update.get(cache_key, datetime.min)
                if datetime.now() - cache_time < timedelta(minutes=5):
                    return self.option_chains_cache[cache_key]
            
            self.logger.info(f"Fetching complete option chain for {symbol} (expiry: {expiry_date})")
            
            instruments_data = self.get_all_instruments()
            
            # Determine exchange
            if symbol == 'SENSEX':
                exchange = 'BFO'
            else:
                exchange = 'NFO'
            
            if exchange not in instruments_data:
                return pd.DataFrame()
            
            exchange_instruments = instruments_data[exchange]
            
            # Filter for symbol's options
            option_instruments = exchange_instruments[
                (exchange_instruments['name'] == symbol) &
                (exchange_instruments['instrument_type'].isin(['CE', 'PE']))
            ].copy()
            
            if option_instruments.empty:
                self.logger.warning(f"No option instruments found for {symbol}")
                return pd.DataFrame()
            
            # Filter by expiry if specified
            if expiry_date:
                expiry_dt = pd.to_datetime(expiry_date).date()
                option_instruments = option_instruments[
                    option_instruments['expiry'].dt.date == expiry_dt
                ]
            else:
                # Get nearest expiry
                current_date = pd.Timestamp.now().date()
                future_expiries = option_instruments[option_instruments['expiry'].dt.date >= current_date]
                if not future_expiries.empty:
                    nearest_expiry = future_expiries['expiry'].min()
                    option_instruments = option_instruments[option_instruments['expiry'] == nearest_expiry]
            
            if option_instruments.empty:
                self.logger.warning(f"No options found for {symbol} with expiry {expiry_date}")
                return pd.DataFrame()
            
            # Get ALL instrument tokens
            instrument_tokens = option_instruments['instrument_token'].tolist()
            
            self.logger.info(f"Fetching quotes for {len(instrument_tokens)} option instruments...")
            
            # Fetch quotes in batches
            batch_size = 500
            all_quotes = {}
            
            for i in range(0, len(instrument_tokens), batch_size):
                batch_tokens = instrument_tokens[i:i + batch_size]
                try:
                    batch_quotes = self.kite.quote(batch_tokens)
                    all_quotes.update(batch_quotes)
                    time.sleep(0.1)  # Rate limit protection
                except Exception as e:
                    self.logger.error(f"Error fetching quotes for batch {i}: {e}")
                    continue
            
            # Build comprehensive option chain
            option_chain_data = []
            
            for _, instrument in option_instruments.iterrows():
                token = str(instrument['instrument_token'])
                
                if token in all_quotes:
                    quote_data = all_quotes[token]
                    
                    # Extract comprehensive data
                    last_price = quote_data.get('last_price', 0)
                    ohlc = quote_data.get('ohlc', {})
                    
                    # Calculate change and percentage
                    close_price = ohlc.get('close', 0)
                    if close_price and close_price != 0:
                        change = last_price - close_price
                        change_percent = (change / close_price) * 100
                    else:
                        change = quote_data.get('net_change', 0)
                        change_percent = 0
                    
                    # Get depth data
                    depth = quote_data.get('depth', {})
                    buy_orders = depth.get('buy', [])
                    sell_orders = depth.get('sell', [])
                    
                    # Volume and OI data
                    raw_volume = quote_data.get('volume', 0)
                    raw_oi = quote_data.get('oi', 0)
                    lot_size = instrument['lot_size']
                    
                    option_data = {
                        'symbol': instrument['tradingsymbol'],
                        'instrument_token': instrument['instrument_token'],
                        'exchange': instrument['exchange'],
                        'strike_price': instrument['strike'],
                        'option_type': instrument['instrument_type'],
                        'expiry': instrument['expiry'].strftime('%Y-%m-%d'),
                        'lot_size': lot_size,
                        
                        # Price data
                        'last_price': last_price,
                        'change': change,
                        'change_percent': change_percent,
                        'open': ohlc.get('open', 0),
                        'high': ohlc.get('high', 0),
                        'low': ohlc.get('low', 0),
                        'close': close_price,
                        
                        # Volume and OI
                        'volume': raw_volume,
                        'volume_lots': raw_volume // lot_size if lot_size > 0 else raw_volume,
                        'oi': raw_oi,
                        'oi_lots': raw_oi // lot_size if lot_size > 0 else raw_oi,
                        'oi_day_high': quote_data.get('oi_day_high', 0),
                        'oi_day_low': quote_data.get('oi_day_low', 0),
                        
                        # Bid/Ask data
                        'bid_price': buy_orders[0]['price'] if buy_orders else 0,
                        'bid_qty': buy_orders[0]['quantity'] if buy_orders else 0,
                        'ask_price': sell_orders[0]['price'] if sell_orders else 0,
                        'ask_qty': sell_orders[0]['quantity'] if sell_orders else 0,
                        
                        # Additional data
                        'implied_volatility': quote_data.get('implied_volatility', 0),
                        'timestamp': quote_data.get('timestamp'),
                        'exchange_timestamp': quote_data.get('exchange_timestamp'),
                    }
                    
                    option_chain_data.append(option_data)
            
            # Create DataFrame
            if option_chain_data:
                df = pd.DataFrame(option_chain_data)
                df = df.sort_values(['strike_price', 'option_type'])
                
                # Cache the result
                self.option_chains_cache[cache_key] = df
                self.last_cache_update[cache_key] = datetime.now()
                
                self.logger.info(f"Fetched complete option chain for {symbol}: {len(df)} options")
                return df
            else:
                return pd.DataFrame()
                
        except Exception as e:
            self.logger.error(f"Error fetching option chain for {symbol}: {e}")
            return pd.DataFrame()
    
    def get_formatted_option_chain_table(self, symbol: str, expiry_date: Optional[str] = None) -> pd.DataFrame:
        """Get option chain formatted as a table (CE and PE side by side)"""
        try:
            # Get complete option chain
            option_chain = self.get_complete_option_chain(symbol, expiry_date)
            
            if option_chain.empty:
                return pd.DataFrame()
            
            # Separate CE and PE options
            ce_options = option_chain[option_chain['option_type'] == 'CE'].copy()
            pe_options = option_chain[option_chain['option_type'] == 'PE'].copy()
            
            # Get all unique strikes
            all_strikes = sorted(option_chain['strike_price'].unique())
            
            # Create formatted table
            formatted_data = []
            
            for strike in all_strikes:
                ce_data = ce_options[ce_options['strike_price'] == strike]
                pe_data = pe_options[pe_options['strike_price'] == strike]
                
                row_data = {'strike_price': strike}
                
                # CE data
                if not ce_data.empty:
                    ce_row = ce_data.iloc[0]
                    row_data.update({
                        'ce_symbol': ce_row['symbol'],
                        'ce_last_price': ce_row['last_price'],
                        'ce_change': ce_row['change'],
                        'ce_change_percent': ce_row['change_percent'],
                        'ce_volume': ce_row['volume_lots'],
                        'ce_oi': ce_row['oi_lots'],
                        'ce_bid': ce_row['bid_price'],
                        'ce_ask': ce_row['ask_price'],
                        'ce_iv': ce_row['implied_volatility'],
                        'ce_high': ce_row['high'],
                        'ce_low': ce_row['low'],
                    })
                else:
                    row_data.update({
                        'ce_symbol': '-', 'ce_last_price': 0, 'ce_change': 0,
                        'ce_change_percent': 0, 'ce_volume': 0, 'ce_oi': 0,
                        'ce_bid': 0, 'ce_ask': 0, 'ce_iv': 0, 'ce_high': 0, 'ce_low': 0
                    })
                
                # PE data
                if not pe_data.empty:
                    pe_row = pe_data.iloc[0]
                    row_data.update({
                        'pe_symbol': pe_row['symbol'],
                        'pe_last_price': pe_row['last_price'],
                        'pe_change': pe_row['change'],
                        'pe_change_percent': pe_row['change_percent'],
                        'pe_volume': pe_row['volume_lots'],
                        'pe_oi': pe_row['oi_lots'],
                        'pe_bid': pe_row['bid_price'],
                        'pe_ask': pe_row['ask_price'],
                        'pe_iv': pe_row['implied_volatility'],
                        'pe_high': pe_row['high'],
                        'pe_low': pe_row['low'],
                    })
                else:
                    row_data.update({
                        'pe_symbol': '-', 'pe_last_price': 0, 'pe_change': 0,
                        'pe_change_percent': 0, 'pe_volume': 0, 'pe_oi': 0,
                        'pe_bid': 0, 'pe_ask': 0, 'pe_iv': 0, 'pe_high': 0, 'pe_low': 0
                    })
                
                formatted_data.append(row_data)
            
            return pd.DataFrame(formatted_data)
            
        except Exception as e:
            self.logger.error(f"Error creating formatted option chain table: {e}")
            return pd.DataFrame()
    
    def get_spot_price(self, symbol: str) -> Tuple[float, float]:
        """Get spot price and previous close for any symbol"""
        try:
            # Map symbols to Kite format
            if symbol in self.indices:
                kite_symbol = self.indices[symbol]
            else:
                # For stocks, use NSE format
                kite_symbol = f"NSE:{symbol}"
            
            quote = self.kite.quote([kite_symbol])
            
            if kite_symbol in quote:
                data = quote[kite_symbol]
                spot_price = data['last_price']
                prev_close = data['ohlc']['close']
                return float(spot_price), float(prev_close)
            else:
                return 0.0, 0.0
                
        except Exception as e:
            self.logger.error(f"Error fetching spot price for {symbol}: {e}")
            return 0.0, 0.0
    
    def export_all_data_to_csv(self, output_dir: str = "kite_data_export"):
        """Export all data to CSV files"""
        try:
            # Create output directory
            os.makedirs(output_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            self.logger.info("Starting comprehensive data export...")
            
            # 1. Export all indices data
            indices_data = self.get_all_indices_data()
            if indices_data:
                indices_df = pd.DataFrame(indices_data).T
                indices_file = os.path.join(output_dir, f"indices_data_{timestamp}.csv")
                indices_df.to_csv(indices_file, index=False)
                self.logger.info(f"Exported indices data to {indices_file}")
            
            # 2. Export stocks list
            stocks_list = self.get_all_stocks_list()
            if stocks_list:
                stocks_df = pd.DataFrame(stocks_list)
                stocks_file = os.path.join(output_dir, f"stocks_list_{timestamp}.csv")
                stocks_df.to_csv(stocks_file, index=False)
                self.logger.info(f"Exported {len(stocks_list)} stocks to {stocks_file}")
            
            # 3. Export option chains for all indices
            for symbol in self.indices.keys():
                try:
                    # Get all expiries for this symbol
                    expiries = self.get_all_expiries_for_symbol(symbol)
                    
                    for expiry in expiries[:3]:  # Export first 3 expiries to avoid too many files
                        option_chain = self.get_complete_option_chain(symbol, expiry)
                        if not option_chain.empty:
                            filename = f"{symbol}_option_chain_{expiry}_{timestamp}.csv"
                            filepath = os.path.join(output_dir, filename)
                            option_chain.to_csv(filepath, index=False)
                            self.logger.info(f"Exported {len(option_chain)} options for {symbol} {expiry}")
                        
                        time.sleep(1)  # Rate limiting
                        
                except Exception as e:
                    self.logger.error(f"Error exporting option chain for {symbol}: {e}")
            
            # 4. Export summary
            summary = {
                'export_timestamp': timestamp,
                'total_indices': len(indices_data) if indices_data else 0,
                'total_stocks': len(stocks_list) if stocks_list else 0,
                'exported_files': len(os.listdir(output_dir))
            }
            
            summary_file = os.path.join(output_dir, f"export_summary_{timestamp}.json")
            with open(summary_file, 'w') as f:
                json.dump(summary, f, indent=2)
            
            self.logger.info(f"Data export completed! Files saved to {output_dir}")
            return output_dir
            
        except Exception as e:
            self.logger.error(f"Error during data export: {e}")
            return None
    
    def get_market_status(self) -> Dict:
        """Get current market status"""
        try:
            # Get market status for different exchanges
            status_data = {}
            
            # Try to get a sample quote to check if market is open
            sample_quote = self.kite.quote(["NSE:NIFTY 50"])
            
            if sample_quote:
                nifty_data = sample_quote["NSE:NIFTY 50"]
                market_timestamp = nifty_data.get('timestamp')
                
                status_data = {
                    'market_open': True,
                    'last_update': market_timestamp,
                    'current_time': datetime.now().isoformat(),
                    'nifty_price': nifty_data['last_price'],
                    'status': 'LIVE' if market_timestamp else 'CLOSED'
                }
            
            return status_data
            
        except Exception as e:
            self.logger.error(f"Error getting market status: {e}")
            return {'market_open': False, 'status': 'ERROR', 'error': str(e)}

def main():
    """Main function to demonstrate the comprehensive Kite API"""
    try:
        print("🚀 Comprehensive Kite API Integration")
        print("=" * 60)
        
        # Initialize API
        api = ComprehensiveKiteAPI()
        
        # Test connection
        profile = api.kite.profile()
        print(f"✅ Connected successfully!")
        print(f"User: {profile['user_name']}")
        print(f"Email: {profile['email']}")
        print(f"Broker: {profile['broker']}")
        
        # Get market status
        print("\n📊 Market Status:")
        market_status = api.get_market_status()
        print(json.dumps(market_status, indent=2))
        
        # Get all indices data
        print("\n📈 All Indices Data:")
        indices_data = api.get_all_indices_data()
        for symbol, data in indices_data.items():
            print(f"{symbol}: ₹{data['last_price']:,.2f} ({data['change']:+.2f}, {data['change_percent']:+.2f}%)")
        
        # Get stocks count
        print("\n📋 Stocks Data:")
        stocks_list = api.get_all_stocks_list()
        print(f"Total tradeable stocks: {len(stocks_list)}")
        print(f"Sample stocks: {[s['symbol'] for s in stocks_list[:10]]}")
        
        # Test option chain for NIFTY
        print("\n⚡ NIFTY Option Chain Sample:")
        nifty_expiries = api.get_all_expiries_for_symbol('NIFTY')
        print(f"Available expiries: {nifty_expiries[:5]}")
        
        if nifty_expiries:
            option_chain = api.get_complete_option_chain('NIFTY', nifty_expiries[0])
            print(f"Option chain for {nifty_expiries[0]}: {len(option_chain)} options")
            
            # Show sample strikes
            if not option_chain.empty:
                strikes = sorted(option_chain['strike_price'].unique())
                print(f"Strike range: {strikes[0]} to {strikes[-1]}")
        
        # Export all data
        print("\n💾 Exporting All Data...")
        export_dir = api.export_all_data_to_csv()
        if export_dir:
            print(f"✅ All data exported to: {export_dir}")
        
        print("\n🎉 Comprehensive Kite API integration completed successfully!")
        print("✅ Real option chain data is now available for all indices and stocks")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
