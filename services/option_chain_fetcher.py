import os
import pandas as pd
from dotenv import load_dotenv
from kiteconnect import KiteConnect
import logging
from datetime import datetime
import time
from backend.services.greeks_calculator import GreeksCalculator

# Load environment variables
load_dotenv()

class OptionChainFetcher:
    def __init__(self):
        """Initialize the Kite API connection"""
        self.api_key = os.getenv('KITE_API_KEY')
        self.api_secret = os.getenv('KITE_API_SECRET')
        self.request_token = os.getenv('KITE_REQUEST_TOKEN')
        self.access_token = os.getenv('KITE_ACCESS_TOKEN')
        
        # Initialize KiteConnect
        self.kite = KiteConnect(api_key=self.api_key)
        
        # Initialize Greeks calculator
        self.greeks_calc = GreeksCalculator()
        
        # Set access token if available
        if self.access_token:
            self.kite.set_access_token(self.access_token)
        else:
            self._generate_access_token()
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def _generate_access_token(self):
        """Generate access token if not available"""
        try:
            data = self.kite.generate_session(self.request_token, api_secret=self.api_secret)
            self.access_token = data["access_token"]
            self.kite.set_access_token(self.access_token)
            self.logger.info("Access token generated successfully")
        except Exception as e:
            self.logger.error(f"Error generating access token: {e}")
            raise
    
    def get_instruments(self, exchange="NFO"):
        """Get all instruments for the given exchange"""
        try:
            # Use BFO for SENSEX, NFO for others
            if exchange == "SENSEX" or exchange == "BFO":
                instruments = self.kite.instruments("BFO")
            else:
                instruments = self.kite.instruments(exchange)
            df = pd.DataFrame(instruments)
            if 'expiry' in df.columns:
                df['expiry'] = pd.to_datetime(df['expiry'])
            return df
        except Exception as e:
            self.logger.error(f"Error fetching instruments: {e}")
            return None
    
    def get_option_chain(self, symbol="NIFTY", expiry_date=None, min_strike=None, max_strike=None):
        """
        Get complete option chain for a given symbol
        
        Args:
            symbol: Symbol name (e.g., NIFTY, BANKNIFTY)
            expiry_date: Expiry date in YYYY-MM-DD format
            min_strike: Minimum strike price to include
            max_strike: Maximum strike price to include
        
        Returns:
            DataFrame with complete option chain
        """
        try:
            # Use BFO for SENSEX, NFO for others
            if symbol == "SENSEX":
                instruments_df = self.get_instruments("BFO")
                # SENSEX options have name 'SENSEX' and exchange 'BFO'
                option_instruments = instruments_df[
                    (instruments_df['name'] == "SENSEX") &
                    (instruments_df['instrument_type'].isin(['CE', 'PE']))
                ].copy()
            else:
                instruments_df = self.get_instruments()
                option_instruments = instruments_df[
                    (instruments_df['name'] == symbol) & 
                    (instruments_df['instrument_type'].isin(['CE', 'PE']))
                ].copy()
            
            self.logger.info(f"Found {len(option_instruments)} option instruments for {symbol}")
            
            if option_instruments.empty:
                self.logger.warning(f"No option instruments found for {symbol}")
                return None
            
            # Filter by strike range if specified
            if min_strike is not None:
                option_instruments = option_instruments[option_instruments['strike'] >= min_strike]
                self.logger.info(f"Filtered strikes >= {min_strike}")
            
            if max_strike is not None:
                option_instruments = option_instruments[option_instruments['strike'] <= max_strike]
                self.logger.info(f"Filtered strikes <= {max_strike}")
            
            if option_instruments.empty:
                self.logger.warning(f"No options found for {symbol} in strike range {min_strike}-{max_strike}")
                return None
            
            if expiry_date:
                # Filter by specific expiry date
                option_instruments = option_instruments[
                    option_instruments['expiry'].dt.strftime('%Y-%m-%d') == expiry_date
                ]
            else:
                # Get nearest expiry
                current_date = pd.Timestamp.now().date()
                future_expiries = option_instruments[option_instruments['expiry'].dt.date >= current_date]
                if not future_expiries.empty:
                    nearest_expiry = future_expiries['expiry'].min()
                    option_instruments = option_instruments[option_instruments['expiry'] == nearest_expiry]
                else:
                    # If no future expiries, get the latest available expiry
                    latest_expiry = option_instruments['expiry'].max()
                    option_instruments = option_instruments[option_instruments['expiry'] == latest_expiry]
            
            if option_instruments.empty:
                self.logger.warning(f"No options found for {symbol}")
                return None
            
            # Get instrument tokens
            instrument_tokens = option_instruments['instrument_token'].tolist()
            
            # Fetch quotes in batches (Kite API has limits)
            batch_size = 500  # Kite allows up to 500 instruments per request
            all_quotes = {}
            
            for i in range(0, len(instrument_tokens), batch_size):
                batch_tokens = instrument_tokens[i:i + batch_size]
                try:
                    quotes = self.kite.quote(batch_tokens)
                    all_quotes.update(quotes)
                    time.sleep(0.1)  # Small delay to avoid rate limits
                except Exception as e:
                    self.logger.error(f"Error fetching quotes for batch {i}: {e}")
                    continue
            
            # Create option chain dataframe
            option_chain_data = []
            
            for _, instrument in option_instruments.iterrows():
                token = str(instrument['instrument_token'])
                if token in all_quotes:
                    quote_data = all_quotes[token]
                    
                    # Calculate percentage change manually since API net_change is often 0
                    last_price = quote_data.get('last_price', 0)
                    close_price = quote_data.get('ohlc', {}).get('close', 0)
                    open_price = quote_data.get('ohlc', {}).get('open', 0)
                    api_net_change = quote_data.get('net_change', 0)
                    
                    # Calculate actual change and percentage
                    if close_price and close_price != 0:
                        # Use previous day close for change calculation
                        actual_change = last_price - close_price
                        change_percent = (actual_change / close_price) * 100
                    elif open_price and open_price != 0:
                        # Fallback to change from today's open if no previous close
                        actual_change = last_price - open_price
                        change_percent = (actual_change / open_price) * 100
                    else:
                        # If no reference price available, use API value (likely 0)
                        actual_change = api_net_change
                        change_percent = 0
                    
                    # Extract bid/ask data safely
                    depth_data = quote_data.get('depth', {})
                    buy_orders = depth_data.get('buy', [])
                    sell_orders = depth_data.get('sell', [])
                    
                    bid_price = buy_orders[0]['price'] if buy_orders else 0
                    bid_qty = buy_orders[0]['quantity'] if buy_orders else 0
                    ask_price = sell_orders[0]['price'] if sell_orders else 0
                    ask_qty = sell_orders[0]['quantity'] if sell_orders else 0
                    
                    # Get volume and OI in lots (divide by lot size)
                    raw_volume = quote_data.get('volume', 0)
                    raw_oi = quote_data.get('oi', 0)
                    raw_oi_day_high = quote_data.get('oi_day_high', 0)
                    raw_oi_day_low = quote_data.get('oi_day_low', 0)
                    lot_size = instrument['lot_size']
                    
                    # Convert to lots for realistic display
                    volume_lots = raw_volume // lot_size if lot_size > 0 else raw_volume
                    oi_lots = raw_oi // lot_size if lot_size > 0 else raw_oi
                    oi_day_high_lots = raw_oi_day_high // lot_size if lot_size > 0 else raw_oi_day_high
                    oi_day_low_lots = raw_oi_day_low // lot_size if lot_size > 0 else raw_oi_day_low
                    
                    # Calculate OI change (current OI - previous day OI estimate)
                    # Using day low as approximation for previous day OI if available
                    if raw_oi_day_low > 0:
                        oi_change = oi_lots - oi_day_low_lots
                    else:
                        oi_change = 0  # No reference available
                    
                    # Get implied volatility if available
                    implied_volatility = quote_data.get('implied_volatility', 0)
                    if implied_volatility == 0:
                        # Try alternative field names that might contain IV
                        implied_volatility = quote_data.get('iv', 0)
                    
                    option_data = {
                        'symbol': instrument['tradingsymbol'],
                        'instrument_token': instrument['instrument_token'],
                        'strike_price': instrument['strike'],
                        'option_type': instrument['instrument_type'],
                        'expiry': instrument['expiry'].strftime('%Y-%m-%d'),
                        'last_price': last_price,
                        'change': actual_change,     # Real calculated change
                        'change_percent': change_percent,  # Real calculated percentage
                        'volume': volume_lots,  # Volume in lots
                        'oi': oi_lots,          # OI in lots
                        'oi_change': oi_change, # Change in OI
                        'implied_volatility': implied_volatility,  # IV
                        'bid_price': bid_price,
                        'bid_qty': bid_qty,
                        'ask_price': ask_price,
                        'ask_qty': ask_qty,
                        'high': quote_data.get('ohlc', {}).get('high', 0),
                        'low': quote_data.get('ohlc', {}).get('low', 0),
                        'open': open_price,
                        'close': close_price,
                    }
                    option_chain_data.append(option_data)
            
            if not option_chain_data:
                self.logger.warning("No quote data found for options")
                return None
            
            option_chain_df = pd.DataFrame(option_chain_data)
            
            # Sort by strike price and option type
            option_chain_df = option_chain_df.sort_values(['strike_price', 'option_type'])
            
            self.logger.info(f"Successfully fetched option chain for {symbol} with {len(option_chain_df)} options")
            return option_chain_df
            
        except Exception as e:
            self.logger.error(f"Error fetching option chain: {e}")
            return None
    
    def get_spot_price(self, symbol):
        """
        Get current spot price for the underlying symbol
        
        Args:
            symbol: Symbol name (e.g., NIFTY, BANKNIFTY)
        
        Returns:
            Current spot price
        """
        try:
            # Symbol mapping for Kite API
            if symbol == "NIFTY":
                instrument_token = 256265  # NIFTY 50 token
            elif symbol == "BANKNIFTY":
                instrument_token = 260105  # BANK NIFTY token
            elif symbol == "FINNIFTY":
                instrument_token = 257801  # FINNIFTY token
            elif symbol == "MIDCPNIFTY":
                instrument_token = 288009  # MIDCAP NIFTY token
            elif symbol == "SENSEX":
                instrument_token = 265  # SENSEX token
            else:
                # For individual stocks, try to get the instrument token
                instruments = self.get_instruments("NSE")
                stock_instrument = instruments[instruments['tradingsymbol'] == symbol]
                if not stock_instrument.empty:
                    instrument_token = stock_instrument.iloc[0]['instrument_token']
                else:
                    self.logger.error(f"Instrument token not found for {symbol}")
                    return None
            
            # Get quote for the instrument
            quote = self.kite.quote([instrument_token])
            if str(instrument_token) in quote:
                spot_price = quote[str(instrument_token)]['last_price']
                self.logger.info(f"Got spot price for {symbol}: {spot_price}")
                return float(spot_price)
            else:
                self.logger.error(f"Quote not found for {symbol} with token {instrument_token}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error fetching spot price for {symbol}: {e}")
            return None

    def get_formatted_option_chain(self, symbol="NIFTY", expiry_date=None, min_strike=None, max_strike=None):
        """
        Get formatted option chain table with CE and PE side by side
        
        Args:
            symbol: Symbol name (e.g., NIFTY, BANKNIFTY)
            expiry_date: Expiry date in YYYY-MM-DD format
            min_strike: Minimum strike price to include
            max_strike: Maximum strike price to include
        
        Returns:
            DataFrame with CE and PE options side by side including Greeks
        """
        try:
            option_chain = self.get_option_chain(symbol, expiry_date, min_strike, max_strike)
            
            if option_chain is None or option_chain.empty:
                return None
            
            # Get spot price for Greeks calculations
            try:
                spot_price_data = self.get_spot_price(symbol)
                if spot_price_data is None or spot_price_data[0] is None:
                    spot_price = None
                    self.logger.warning(f"Could not get spot price for {symbol}, Greeks will not be calculated")
                else:
                    spot_price = spot_price_data[0]  # Take the current price from tuple
                    self.logger.info(f"Got spot price for {symbol}: {spot_price}")
            except Exception as e:
                self.logger.error(f"Error getting spot price for {symbol}: {e}")
                spot_price = None
            
            # Get expiry date for time calculation
            if option_chain.empty:
                return None
            try:
                expiry_str = option_chain.iloc[0]['expiry']
                time_to_expiry = self.greeks_calc.calculate_time_to_expiry(expiry_str)
                self.logger.info(f"Calculated time to expiry: {time_to_expiry} for {expiry_str}")
            except Exception as e:
                self.logger.error(f"Error calculating time to expiry: {e}")
                time_to_expiry = 0.1  # Default 36 days
            
            # Separate CE and PE options
            ce_options = option_chain[option_chain['option_type'] == 'CE'].copy()
            pe_options = option_chain[option_chain['option_type'] == 'PE'].copy()
            
            # Create formatted table
            formatted_data = []
            
            # Get all unique strike prices
            all_strikes = sorted(option_chain['strike_price'].unique())
            
            for strike in all_strikes:
                ce_data = ce_options[ce_options['strike_price'] == strike]
                pe_data = pe_options[pe_options['strike_price'] == strike]
                
                row_data = {
                    'strike_price': strike,
                }
                
                # CE data
                if not ce_data.empty:
                    ce_row = ce_data.iloc[0]
                    
                    # Calculate CE Greeks with improved error handling
                    ce_greeks = {'delta': 0, 'gamma': 0, 'vega': 0, 'theta': 0, 'rho': 0, 'iv': 0}
                    ce_analytics = {'intrinsic': 0, 'time_value': 0, 'wtb_percent': 0, 'wtt_percent': 0, 'target_price': 0, 'stop_loss': 0}
                    ce_signal = 'HOLD'
                    
                    try:
                        # Ensure IV is a number
                        ce_iv = ce_row['implied_volatility']
                        if isinstance(ce_iv, (list, tuple)):
                            ce_iv = ce_iv[0] if ce_iv else 0
                        ce_iv = float(ce_iv) if ce_iv else 0
                        ce_greeks['iv'] = ce_iv
                        
                        # Calculate Greeks if we have required data
                        if spot_price and spot_price > 0 and time_to_expiry > 0:
                            ce_greeks = self.greeks_calc.calculate_all_greeks(
                                S=float(spot_price),
                                K=float(strike),
                                T=float(time_to_expiry),
                                r=0.05,  # 5% risk-free rate
                                sigma=ce_iv if ce_iv > 0 else None,
                                option_type='CE',
                                option_price=float(ce_row['last_price'])
                            )
                            
                            # Calculate analytics
                            ce_analytics = self.greeks_calc.calculate_analytics(
                                S=float(spot_price),
                                K=float(strike),
                                option_price=float(ce_row['last_price']),
                                option_type='CE'
                            )
                            
                            # Calculate entry signal
                            ce_signal = self.greeks_calc.calculate_entry_signal(
                                delta=ce_greeks['delta'],
                                iv=ce_greeks['iv'],
                                wtb_percent=ce_analytics['wtb_percent']
                            )
                    except Exception as e:
                        self.logger.error(f"Error calculating CE Greeks for strike {strike}: {e}")
                        ce_greeks = {'delta': 0, 'gamma': 0, 'vega': 0, 'theta': 0, 'rho': 0, 'iv': 0}
                    
                    row_data.update({
                        'ce_symbol': ce_row['symbol'],
                        'ce_bid': ce_row['bid_price'],
                        'ce_ask': ce_row['ask_price'],
                        'ce_bid_qty': ce_row['bid_qty'],
                        'ce_ask_qty': ce_row['ask_qty'],
                        'ce_last_price': ce_row['last_price'],
                        'ce_change': ce_row['change'],
                        'ce_change_percent': ce_row['change_percent'],
                        'ce_volume': ce_row['volume'],
                        'ce_oi': ce_row['oi'],
                        'ce_oi_change': ce_row['oi_change'],
                        'ce_iv': ce_greeks['iv'],
                        'ce_delta': ce_greeks['delta'],
                        'ce_gamma': ce_greeks['gamma'],
                        'ce_vega': ce_greeks['vega'],
                        'ce_theta': ce_greeks['theta'],
                        'ce_rho': ce_greeks['rho'],
                        'ce_intrinsic': ce_analytics['intrinsic'],
                        'ce_time_value': ce_analytics['time_value'],
                        'ce_wtb_percent': ce_analytics['wtb_percent'],
                        'ce_wtt_percent': ce_analytics['wtt_percent'],
                        'ce_target_price': ce_analytics['target_price'],
                        'ce_stop_loss': ce_analytics['stop_loss'],
                        'ce_signal': ce_signal,
                        'ce_high': ce_row['high'],
                        'ce_low': ce_row['low'],
                    })
                else:
                    row_data.update({
                        'ce_symbol': '-',
                        'ce_bid': 0,
                        'ce_ask': 0,
                        'ce_bid_qty': 0,
                        'ce_ask_qty': 0,
                        'ce_last_price': 0,
                        'ce_change': 0,
                        'ce_change_percent': 0,
                        'ce_volume': 0,
                        'ce_oi': 0,
                        'ce_oi_change': 0,
                        'ce_iv': 0,
                        'ce_delta': 0,
                        'ce_gamma': 0,
                        'ce_vega': 0,
                        'ce_theta': 0,
                        'ce_rho': 0,
                        'ce_intrinsic': 0,
                        'ce_time_value': 0,
                        'ce_wtb_percent': 0,
                        'ce_wtt_percent': 0,
                        'ce_target_price': 0,
                        'ce_stop_loss': 0,
                        'ce_signal': 'HOLD',
                        'ce_high': 0,
                        'ce_low': 0,
                    })
                
                # PE data
                if not pe_data.empty:
                    pe_row = pe_data.iloc[0]
                    
                    # Calculate PE Greeks
                    pe_greeks = {'delta': 0, 'gamma': 0, 'vega': 0, 'theta': 0, 'rho': 0, 'iv': 0}
                    pe_analytics = {'intrinsic': 0, 'time_value': 0, 'wtb_percent': 0, 'wtt_percent': 0, 'target_price': 0, 'stop_loss': 0}
                    pe_signal = 'HOLD'
                    
                    try:
                        # Ensure IV is a number
                        pe_iv = pe_row['implied_volatility']
                        if isinstance(pe_iv, (list, tuple)):
                            pe_iv = pe_iv[0] if pe_iv else 0
                        pe_iv = float(pe_iv) if pe_iv else 0
                        pe_greeks['iv'] = pe_iv
                        
                        if spot_price and spot_price > 0 and time_to_expiry > 0:
                            pe_greeks = self.greeks_calc.calculate_all_greeks(
                                S=float(spot_price),
                                K=float(strike),
                                T=float(time_to_expiry),
                                r=0.05,  # 5% risk-free rate
                                sigma=pe_iv if pe_iv > 0 else None,
                                option_type='PE',
                                option_price=float(pe_row['last_price'])
                            )
                            
                            # Calculate analytics
                            pe_analytics = self.greeks_calc.calculate_analytics(
                                S=float(spot_price),
                                K=float(strike),
                                option_price=float(pe_row['last_price']),
                                option_type='PE'
                            )
                            
                            # Calculate entry signal
                            pe_signal = self.greeks_calc.calculate_entry_signal(
                                delta=pe_greeks['delta'],
                                iv=pe_greeks['iv'],
                                wtb_percent=pe_analytics['wtb_percent']
                            )
                    except Exception as e:
                        self.logger.error(f"Error calculating PE Greeks for strike {strike}: {e}")
                        pe_greeks = {'delta': 0, 'gamma': 0, 'vega': 0, 'theta': 0, 'rho': 0, 'iv': 0}
                    
                    row_data.update({
                        'pe_symbol': pe_row['symbol'],
                        'pe_bid': pe_row['bid_price'],
                        'pe_ask': pe_row['ask_price'],
                        'pe_bid_qty': pe_row['bid_qty'],
                        'pe_ask_qty': pe_row['ask_qty'],
                        'pe_last_price': pe_row['last_price'],
                        'pe_change': pe_row['change'],
                        'pe_change_percent': pe_row['change_percent'],
                        'pe_volume': pe_row['volume'],
                        'pe_oi': pe_row['oi'],
                        'pe_oi_change': pe_row['oi_change'],
                        'pe_iv': pe_greeks['iv'],
                        'pe_delta': pe_greeks['delta'],
                        'pe_gamma': pe_greeks['gamma'],
                        'pe_vega': pe_greeks['vega'],
                        'pe_theta': pe_greeks['theta'],
                        'pe_rho': pe_greeks['rho'],
                        'pe_intrinsic': pe_analytics['intrinsic'],
                        'pe_time_value': pe_analytics['time_value'],
                        'pe_wtb_percent': pe_analytics['wtb_percent'],
                        'pe_wtt_percent': pe_analytics['wtt_percent'],
                        'pe_target_price': pe_analytics['target_price'],
                        'pe_stop_loss': pe_analytics['stop_loss'],
                        'pe_signal': pe_signal,
                        'pe_high': pe_row['high'],
                        'pe_low': pe_row['low'],
                    })
                else:
                    row_data.update({
                        'pe_symbol': '-',
                        'pe_bid': 0,
                        'pe_ask': 0,
                        'pe_bid_qty': 0,
                        'pe_ask_qty': 0,
                        'pe_last_price': 0,
                        'pe_change': 0,
                        'pe_change_percent': 0,
                        'pe_volume': 0,
                        'pe_oi': 0,
                        'pe_oi_change': 0,
                        'pe_iv': 0,
                        'pe_delta': 0,
                        'pe_gamma': 0,
                        'pe_vega': 0,
                        'pe_theta': 0,
                        'pe_rho': 0,
                        'pe_intrinsic': 0,
                        'pe_time_value': 0,
                        'pe_wtb_percent': 0,
                        'pe_wtt_percent': 0,
                        'pe_target_price': 0,
                        'pe_stop_loss': 0,
                        'pe_signal': 'HOLD',
                        'pe_high': 0,
                        'pe_low': 0,
                    })
                
                formatted_data.append(row_data)
            
            formatted_df = pd.DataFrame(formatted_data)
            return formatted_df
            
        except Exception as e:
            self.logger.error(f"Error creating formatted option chain: {e}")
            return None
    
    def save_option_chain_to_csv(self, symbol="NIFTY", expiry_date=None, filename=None, min_strike=None, max_strike=None):
        """Save option chain to CSV file"""
        try:
            option_chain = self.get_formatted_option_chain(symbol, expiry_date, min_strike, max_strike)
            
            if option_chain is None:
                self.logger.error("No option chain data to save")
                return False
            
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{symbol}_option_chain_{timestamp}.csv"
            
            option_chain.to_csv(filename, index=False)
            self.logger.info(f"Option chain saved to {filename}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving option chain: {e}")
            return False
    
    def display_option_chain(self, symbol="NIFTY", expiry_date=None, num_strikes=20, min_strike=None, max_strike=None):
        """Display option chain in a formatted table"""
        try:
            option_chain = self.get_formatted_option_chain(symbol, expiry_date, min_strike, max_strike)
            
            if option_chain is None:
                print("No option chain data available")
                return
            
            # Get current spot price (approximate from ATM options)
            mid_index = len(option_chain) // 2
            start_index = max(0, mid_index - num_strikes // 2)
            end_index = min(len(option_chain), start_index + num_strikes)
            
            display_df = option_chain.iloc[start_index:end_index].copy()
            
            print(f"\n{'='*150}")
            print(f"OPTION CHAIN FOR {symbol}")
            if not display_df.empty:
                # Get expiry from the first row that has data
                ce_symbol = display_df.iloc[0]['ce_symbol']
                if ce_symbol != '-':
                    # Extract expiry from symbol (format: NIFTY25JULXXCE)
                    try:
                        symbol_parts = ce_symbol.split('CE')[0] if 'CE' in ce_symbol else ce_symbol.split('PE')[0]
                        expiry_str = symbol_parts[len(symbol):]  # Remove symbol name
                        print(f"Expiry: {expiry_str}")
                    except:
                        print(f"Expiry: Current Week")
                else:
                    print(f"Expiry: Current Week")
            else:
                print(f"Expiry: N/A")
            print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'='*150}")
            
            # Format the display
            print(f"{'CE DATA':<60} {'STRIKE':<10} {'PE DATA':<60}")
            print(f"{'-'*60} {'-'*10} {'-'*60}")
            print(f"{'Symbol':<15} {'Bid':<8} {'Ask':<8} {'LTP':<8} {'Chg':<8} {'Vol':<8} {'OI':<8} {'Strike':<10} "
                  f"{'Symbol':<15} {'Bid':<8} {'Ask':<8} {'LTP':<8} {'Chg':<8} {'Vol':<8} {'OI':<8}")
            print(f"{'-'*130}")
            
            for _, row in display_df.iterrows():
                print(f"{str(row['ce_symbol'])[:14]:<15} "
                      f"{row['ce_bid']:>7.2f} "
                      f"{row['ce_ask']:>7.2f} "
                      f"{row['ce_last_price']:>7.2f} "
                      f"{row['ce_change']:>7.2f} "
                      f"{row['ce_volume']:>7.0f} "
                      f"{row['ce_oi']:>7.0f} "
                      f"{row['strike_price']:>9.0f} "
                      f"{str(row['pe_symbol'])[:14]:<15} "
                      f"{row['pe_bid']:>7.2f} "
                      f"{row['pe_ask']:>7.2f} "
                      f"{row['pe_last_price']:>7.2f} "
                      f"{row['pe_change']:>7.2f} "
                      f"{row['pe_volume']:>7.0f} "
                      f"{row['pe_oi']:>7.0f}")
            
            print(f"{'-'*130}")
            
        except Exception as e:
            self.logger.error(f"Error displaying option chain: {e}")
    
    def get_expiry_dates(self, symbol):
        """Return list of expiry dates for the given symbol"""
        try:
            # Use BFO for SENSEX, NFO for others
            if symbol == "SENSEX":
                instruments_df = self.get_instruments("BFO")
                symbol_instruments = instruments_df[instruments_df['name'] == "SENSEX"]
            else:
                instruments_df = self.get_instruments()
                symbol_instruments = instruments_df[instruments_df['name'] == symbol]
            
            if symbol_instruments.empty:
                self.logger.warning(f"No instruments found for {symbol}")
                return []
            
            # Extract unique expiry dates
            expiry_dates = symbol_instruments['expiry'].dt.date.unique()
            
            # Sort and return as list
            return sorted(expiry_dates.tolist())
        
        except Exception as e:
            self.logger.error(f"Error fetching expiry dates: {e}")
            return []
    
    def get_all_expiry_option_chains(self, symbol="NIFTY", min_strike=None, max_strike=None):
        """
        Fetch formatted option chain tables for all expiry dates for a symbol.
        Returns a dict: {expiry_date: DataFrame}
        """
        try:
            expiry_dates = self.get_expiry_dates(symbol)
            all_chains = {}
            for expiry in expiry_dates:
                expiry_str = expiry.strftime('%Y-%m-%d')
                chain = self.get_formatted_option_chain(symbol, expiry_date=expiry_str, min_strike=min_strike, max_strike=max_strike)
                if chain is not None and not chain.empty:
                    all_chains[expiry_str] = chain
            return all_chains
        except Exception as e:
            self.logger.error(f"Error fetching all expiry option chains: {e}")
            return {}

    def get_spot_price(self, symbol):
        """
        Fetch spot price and previous close for the given symbol using Kite API.
        Returns (spot_price, prev_close)
        """
        try:
            # Map index symbols to instrument token
            instrument_map = {
                "NIFTY": "NSE:NIFTY 50",
                "BANKNIFTY": "NSE:NIFTY BANK",
                "FINNIFTY": "NSE:NIFTY FIN SERVICE",
                "MIDCPNIFTY": "NSE:NIFTY MID SELECT",
                "SENSEX": "BSE:SENSEX"
            }
            if symbol in instrument_map:
                kite_symbol = instrument_map[symbol]
            else:
                # For stocks, use NSE:<SYMBOL>
                kite_symbol = f"NSE:{symbol}"
            quote = self.kite.quote([kite_symbol])
            data = quote[kite_symbol]
            spot_price = data['last_price']
            prev_close = data['ohlc']['close']
            return spot_price, prev_close
        except Exception as e:
            self.logger.error(f"Error fetching spot price for {symbol}: {e}")
            return None, None


def main():
    """Main function to demonstrate the option chain fetcher"""
    try:
        # Initialize the option chain fetcher
        fetcher = OptionChainFetcher()
        
        # Test connection
        print("Testing Kite API connection...")
        profile = fetcher.kite.profile()
        print(f"Connected successfully! User: {profile['user_name']}")
        
        # Get and display NIFTY option chain with strike range 22950-27400
        print("\nFetching NIFTY option chain (strikes 22950-27400)...")
        fetcher.display_option_chain("NIFTY", num_strikes=50, min_strike=22950, max_strike=27400)
        
        # Save to CSV with strike range
        print("\nSaving option chain to CSV (strikes 22950-27400)...")
        fetcher.save_option_chain_to_csv("NIFTY", min_strike=22950, max_strike=27400)
        
        # Get BANKNIFTY option chain
        print("\nFetching BANKNIFTY option chain...")
        fetcher.display_option_chain("BANKNIFTY", num_strikes=20)
        
        # Get expiry dates for NIFTY
        print("\nFetching expiry dates for NIFTY...")
        expiry_dates = fetcher.get_expiry_dates("NIFTY")
        print(f"Expiry dates for NIFTY: {expiry_dates}")
        
        # Get all expiry option chains for NIFTY
        print("\nFetching all expiry option chains for NIFTY...")
        all_chains = fetcher.get_all_expiry_option_chains("NIFTY", min_strike=22950, max_strike=27400)
        for expiry, chain in all_chains.items():
            print(f"\nOption chain for expiry {expiry}:")
            print(chain)
        
        # Get spot price for NIFTY
        print("\nFetching spot price for NIFTY...")
        spot_price, prev_close = fetcher.get_spot_price("NIFTY")
        print(f"Spot Price: {spot_price}, Previous Close: {prev_close}")
        
        # To fetch SENSEX option chain:
        # fetcher = OptionChainFetcher()
        # sensex_chain = fetcher.get_formatted_option_chain("SENSEX")
        
    except Exception as e:
        print(f"Error in main: {e}")

if __name__ == "__main__":
    main()