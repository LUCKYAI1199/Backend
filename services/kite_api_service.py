"""
Kite API Service for fetching real option chain data
"""

import os
import logging
import threading
import time
import json
from pathlib import Path
import pandas as pd
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple, Any
from kiteconnect import KiteConnect
from dotenv import load_dotenv
from config.settings import Config
from services.kite_token_service import kite_token_service
from services.greeks_calculator import GreeksCalculator
from utils.number_converter import convert_abbreviated_to_exact, convert_volume_oi_data

# Load environment variables
load_dotenv()

class KiteAPIService:
    """Service to fetch real option chain data using Kite API"""
    
    def __init__(self):
        """Initialize Kite API connection"""
        self.api_key = Config.KITE_API_KEY
        self.api_secret = Config.KITE_API_SECRET
        self.access_token = Config.KITE_ACCESS_TOKEN
        self.request_token = Config.KITE_REQUEST_TOKEN
        
        # Initialize KiteConnect
        self.kite = KiteConnect(api_key=self.api_key)
        
        # Prefer DB-stored token
        if not kite_token_service.set_access_on_client(self.kite):
            # Fallback to env; bootstrap only if request_token explicitly provided
            if self.access_token:
                self.kite.set_access_token(self.access_token)
            elif self.request_token:
                self._generate_access_token()
        
        # Initialize Greeks calculator
        self.greeks_calculator = GreeksCalculator()
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Cache for instruments
        self._instruments_cache = {}
        self._instruments_cache_time = None
        
    # Cache for quotes (short-lived)
        self._quotes_cache = {}
        self._quotes_cache_time = {}
    # Session OHLC cache for per-instrument aggregation
        self._session_ohlc = {}
        self._session_day = None
    # Cache for previous day option candles (per token, per trading day)
        self._option_prev_day_cache = {}
    # Cache for current day intraday (true) OHLC per option token (per token, refreshed periodically)
        self._option_today_cache = {}
    # Cache for recent daily history per underlying symbol (TTL)
        self._daily_history_cache = {}
    # Simple rate-limit cooldowns to avoid hammering historical endpoints
        self._rate_limit_prevday_cooldown_until: Optional[datetime] = None
        self._rate_limit_intraday_cooldown_until: Optional[datetime] = None
    # Background warm jobs tracker for prev-day cache
        self._prevday_warm_jobs: Dict[str, Dict[str, Any]] = {}
    # Disk cache for prev-day OHLC to speed up restarts
        self._prevday_cache_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'cache')
        try:
            os.makedirs(self._prevday_cache_dir, exist_ok=True)
        except Exception:
            pass
        self._prevday_cache_lock = threading.Lock()
        self._load_prevday_cache_for_today()

    def _ensure_session(self):
        """Ensure Kite client has a valid access token; refresh if needed."""
        try:
            kite_token_service.ensure_valid(self.kite)
        except Exception:
            # Best-effort; actual calls will still raise if invalid
            pass

    def _reset_session_if_needed(self):
        today = datetime.now().date()
        if self._session_day != today:
            self._session_day = today
            self._session_ohlc.clear()
            self.logger.info("[SessionOHLC] Reset for new trading day")

    def _update_session_ohlc(self, token: int, ltp: float):
        if not ltp or ltp <= 0:
            return
        self._reset_session_if_needed()
        rec = self._session_ohlc.get(token)
        if rec is None:
            # Initialize with placeholders; previous day values fetched lazily if possible
            self._session_ohlc[token] = {'open': ltp, 'high': ltp, 'low': ltp, 'close': ltp}
        else:
            if ltp > rec['high']:
                rec['high'] = ltp
            if ltp < rec['low']:
                rec['low'] = ltp
            rec['close'] = ltp

    def _first_positive(self, *vals):
        """Return first value > 0 from vals; otherwise None."""
        for v in vals:
            try:
                if v is not None and float(v) > 0:
                    return v
            except Exception:
                continue
        return None
        
    def _calculate_analysis_fields(self, option_type: str, ltp: float, spot_price: float, 
                                 strike: float, delta: float, gamma: float, theta: float, 
                                 vega: float, time_to_expiry: float) -> Dict[str, Any]:
        """Calculate additional analysis fields for options"""
        try:
            # Calculate intrinsic value
            if option_type == 'CE':
                intrinsic = max(0, spot_price - strike)
            else:  # PE
                intrinsic = max(0, strike - spot_price)
            
            # Calculate time value
            time_val = max(0, ltp - intrinsic)
            
            # Calculate buy/sell percentages (simple momentum indicator)
            # This is a simplified version - you can enhance with actual bid/ask analysis
            buy_percent = min(100, max(0, (delta * 100) if option_type == 'CE' else (abs(delta) * 100)))
            sell_percent = 100 - buy_percent
            
            # Calculate target prices (TP1, TP2, TP3) based on delta and gamma
            price_move_1 = spot_price * 0.01  # 1% move
            price_move_2 = spot_price * 0.02  # 2% move
            price_move_3 = spot_price * 0.03  # 3% move
            
            if option_type == 'CE':
                tp1 = ltp + (delta * price_move_1)
                tp2 = ltp + (delta * price_move_2) + (0.5 * gamma * price_move_2 * price_move_2)
                tp3 = ltp + (delta * price_move_3) + (0.5 * gamma * price_move_3 * price_move_3)
            else:  # PE
                tp1 = ltp + (abs(delta) * price_move_1)
                tp2 = ltp + (abs(delta) * price_move_2) + (0.5 * gamma * price_move_2 * price_move_2)
                tp3 = ltp + (abs(delta) * price_move_3) + (0.5 * gamma * price_move_3 * price_move_3)
            
            # Calculate stop loss (based on theta decay and volatility)
            stop_loss = max(0, ltp - (abs(theta) * 2) - (ltp * 0.1))  # 10% or theta-based
            
            # Determine signal type based on Greeks combination
            signal_type = "HOLD"
            signal_strength = 3  # Default neutral (1-5 scale)
            signal_quality = "moderate"
            signal_confidence = "medium"
            
            # Signal logic based on Greeks and price analysis
            if abs(delta) > 0.7:
                if option_type == 'CE' and delta > 0.7:
                    signal_type = "BUY"
                    signal_strength = 5  # Strong buy
                elif option_type == 'PE' and abs(delta) > 0.7:
                    signal_type = "BUY"
                    signal_strength = 5  # Strong buy for puts
            elif abs(delta) > 0.5:
                if option_type == 'CE' and delta > 0.5:
                    signal_type = "BUY"
                    signal_strength = 4  # Moderate buy
                elif option_type == 'PE' and abs(delta) > 0.5:
                    signal_type = "BUY"
                    signal_strength = 4  # Moderate buy for puts
            elif abs(delta) > 0.3:
                if option_type == 'CE' and delta > 0.3:
                    signal_type = "HOLD"
                    signal_strength = 3  # Hold with slight bullish bias
                elif option_type == 'PE' and abs(delta) > 0.3:
                    signal_type = "HOLD"
                    signal_strength = 3  # Hold with slight bearish bias
            else:
                # Low delta options
                if abs(theta) > 0.05:  # High time decay
                    signal_type = "SELL"
                    signal_strength = 2  # Weak sell due to time decay
                else:
                    signal_type = "HOLD"
                    signal_strength = 3  # Neutral hold
            
            # Adjust signal quality based on gamma and vega
            if gamma > 0.01 and vega > 0.1:
                signal_quality = "strong"
                signal_confidence = "high"
            elif gamma > 0.005 or vega > 0.05:
                signal_quality = "moderate"
                signal_confidence = "medium"
            else:
                signal_quality = "weak"
                signal_confidence = "low"
            
            # Adjust for time decay
            if abs(theta) > 0.05:
                if signal_strength > 3:
                    signal_strength = max(1, signal_strength - 1)  # Reduce strength for high time decay
                elif signal_strength <= 3:
                    signal_type = "SELL"
                    signal_strength = max(1, signal_strength - 1)
            
            # Ensure signal strength is within 1-5 range
            signal_strength = max(1, min(5, signal_strength))
            
            return {
                'intrinsic': round(intrinsic, 2),
                'time_val': round(time_val, 2),
                'buy_percent': round(buy_percent, 2),
                'sell_percent': round(sell_percent, 2),
                'tp1': round(tp1, 2),
                'tp2': round(tp2, 2),
                'tp3': round(tp3, 2),
                'stop_loss': round(stop_loss, 2),
                'signal_type': signal_type,
                'signal_strength': signal_strength,  # Now integer 1-5
                'signal_quality': signal_quality,
                'signal_confidence': signal_confidence
            }
            
        except Exception as e:
            self.logger.warning(f"Error calculating analysis fields: {e}")
            return {
                'intrinsic': 0,
                'time_val': 0,
                'buy_percent': 0,
                'sell_percent': 0,
                'tp1': 0,
                'tp2': 0,
                'tp3': 0,
                'stop_loss': 0,
                'signal_type': 'HOLD',
                'signal_strength': 3,  # Default neutral integer
                'signal_quality': 'moderate',
                'signal_confidence': 'medium'
            }
        
        self.logger.info("Kite API Service initialized successfully")
    
    def _generate_access_token(self):
        """Generate access token if not available"""
        try:
            if not self.request_token:
                raise ValueError("Request token not available. Please provide KITE_REQUEST_TOKEN in .env file")
            
            data = self.kite.generate_session(self.request_token, api_secret=self.api_secret)
            self.access_token = data["access_token"]
            self.kite.set_access_token(self.access_token)
            
            # Update .env file with new access token
            self._update_env_file('KITE_ACCESS_TOKEN', self.access_token)
            
            self.logger.info("✅ Access token generated and saved successfully")
        except Exception as e:
            self.logger.error(f"❌ Error generating access token: {e}")
            raise
    
    def _update_env_file(self, key: str, value: str):
        """Update .env file with new value"""
        try:
            env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
            
            # Read current content
            if os.path.exists(env_path):
                with open(env_path, 'r') as f:
                    lines = f.readlines()
            else:
                lines = []
            
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
    
    def _get_instruments(self, exchange: str = "NFO") -> pd.DataFrame:
        """Get instruments for the given exchange with caching"""
        try:
            # Check cache
            current_time = datetime.now()
            if (self._instruments_cache_time and 
                exchange in self._instruments_cache and
                (current_time - self._instruments_cache_time).seconds < 3600):  # 1 hour cache
                return self._instruments_cache[exchange]
            
            # Fetch fresh data
            self.logger.info(f"Fetching instruments for {exchange}...")
            instruments = self.kite.instruments(exchange)
            df = pd.DataFrame(instruments)
            
            # Cache the result
            self._instruments_cache[exchange] = df
            self._instruments_cache_time = current_time
            
            self.logger.info(f"✅ Fetched {len(df)} instruments for {exchange}")
            return df
            
        except Exception as e:
            self.logger.error(f"❌ Error fetching instruments for {exchange}: {e}")
            return pd.DataFrame()
    
    def get_all_symbols(self) -> Dict[str, List[str]]:
        """Get all available symbols categorized by type - REAL DATA from Kite API"""
        try:
            self._ensure_session()
            # Get real symbols from Kite API instruments
            self.logger.info("Fetching ALL real symbols from Kite API...")
            
            # Get instruments from all exchanges
            nse_instruments = self._get_instruments("NSE")
            bse_instruments = self._get_instruments("BSE")
            nfo_instruments = self._get_instruments("NFO")
            bfo_instruments = self._get_instruments("BFO")
            mcx_instruments = self._get_instruments("MCX")
            
            # Extract indices (these are predefined)
            real_indices = []
            for symbol in ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY', 'SENSEX']:
                try:
                    # Check if we can get spot price (validates symbol exists)
                    spot_data = self.get_spot_price(symbol)
                    if spot_data['spot_price'] > 0:
                        real_indices.append(symbol)
                except:
                    continue
            
            # Extract all equity stocks from NSE
            real_stocks = []
            if not nse_instruments.empty:
                equity_stocks = nse_instruments[
                    (nse_instruments['instrument_type'] == 'EQ') &
                    (nse_instruments['segment'] == 'NSE')
                ]['tradingsymbol'].unique()
                real_stocks = sorted(equity_stocks.tolist())
            
            # Get stocks that have options (more liquid stocks)
            stocks_with_options = []
            if not nfo_instruments.empty:
                option_stocks = nfo_instruments[
                    (nfo_instruments['instrument_type'].isin(['CE', 'PE'])) &
                    (~nfo_instruments['name'].isin(['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY']))
                ]['name'].unique()
                stocks_with_options = sorted(option_stocks.tolist())
            
            # Extract MCX commodities
            real_commodities = []
            mcx_commodities = ['COPPER', 'CRUDEOIL', 'CRUDEOILM', 'GOLD', 'GOLDM', 
                              'NATGASMINI', 'NATURALGAS', 'SILVER', 'SILVERM', 'ZINC']
            
            # Check if MCX instruments are available
            if not mcx_instruments.empty:
                for commodity in mcx_commodities:
                    try:
                        # Check if commodity exists in MCX instruments
                        matching_instruments = mcx_instruments[
                            (mcx_instruments['name'].str.contains(commodity, case=False, na=False)) |
                            (mcx_instruments['tradingsymbol'].str.contains(commodity, case=False, na=False))
                        ]
                        if not matching_instruments.empty:
                            real_commodities.append(commodity)
                    except Exception as e:
                        self.logger.warning(f"Error checking MCX commodity {commodity}: {e}")
                        continue
            else:
                self.logger.warning("MCX instruments not available, skipping commodity validation")
            
            # Combine all symbols
            all_symbols = real_indices + real_stocks + real_commodities
            
            result = {
                'indices': real_indices,
                'stocks': real_stocks,
                'commodities': real_commodities,
                'stocks_with_options': stocks_with_options,
                'all': all_symbols,
                'total_indices': len(real_indices),
                'total_stocks': len(real_stocks),
                'total_commodities': len(real_commodities),
                'total_stocks_with_options': len(stocks_with_options),
                'total_symbols': len(all_symbols),
                'last_updated': datetime.now().isoformat()
            }
            
            self.logger.info(f"✅ Fetched {len(real_indices)} indices, {len(real_stocks)} stocks, {len(real_commodities)} commodities, {len(stocks_with_options)} stocks with options")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Error getting real symbols: {e}")
            # Fallback to configured symbols
            return {
                'indices': Config.INDEX_SYMBOLS,
                'stocks': Config.STOCK_SYMBOLS,
                'stocks_with_options': [],
                'all': Config.ALL_SYMBOLS,
                'error': str(e)
            }
    
    def get_all_expiries_for_all_symbols(self) -> Dict[str, List[str]]:
        """Get all expiry dates for ALL symbols that have options"""
        try:
            self._ensure_session()
            self.logger.info("Fetching ALL expiries for ALL symbols...")
            
            # Get option instruments from NFO and BFO
            nfo_instruments = self._get_instruments("NFO")
            bfo_instruments = self._get_instruments("BFO")
            
            all_expiries = {}
            
            # Process NFO instruments (NIFTY, BANKNIFTY, FINNIFTY, MIDCPNIFTY + stocks)
            if not nfo_instruments.empty:
                option_instruments = nfo_instruments[
                    nfo_instruments['instrument_type'].isin(['CE', 'PE'])
                ]
                
                for symbol in option_instruments['name'].unique():
                    symbol_instruments = option_instruments[option_instruments['name'] == symbol]
                    
                    if 'expiry' in symbol_instruments.columns:
                        # Handle different date formats
                        if pd.api.types.is_datetime64_any_dtype(symbol_instruments['expiry']):
                            expiry_dates = symbol_instruments['expiry'].dt.strftime('%Y-%m-%d').unique()
                        else:
                            # Convert to datetime first if it's not already
                            symbol_instruments_copy = symbol_instruments.copy()
                            symbol_instruments_copy['expiry'] = pd.to_datetime(symbol_instruments_copy['expiry'])
                            expiry_dates = symbol_instruments_copy['expiry'].dt.strftime('%Y-%m-%d').unique()
                        
                        all_expiries[symbol] = sorted(expiry_dates)
            
            # Process BFO instruments (SENSEX)
            if not bfo_instruments.empty:
                sensex_instruments = bfo_instruments[
                    (bfo_instruments['name'] == 'SENSEX') &
                    (bfo_instruments['instrument_type'].isin(['CE', 'PE']))
                ]
                
                if not sensex_instruments.empty and 'expiry' in sensex_instruments.columns:
                    # Handle different date formats for SENSEX
                    if pd.api.types.is_datetime64_any_dtype(sensex_instruments['expiry']):
                        expiry_dates = sensex_instruments['expiry'].dt.strftime('%Y-%m-%d').unique()
                    else:
                        sensex_copy = sensex_instruments.copy()
                        sensex_copy['expiry'] = pd.to_datetime(sensex_copy['expiry'])
                        expiry_dates = sensex_copy['expiry'].dt.strftime('%Y-%m-%d').unique()
                    
                    all_expiries['SENSEX'] = sorted(expiry_dates)
            
            # Filter out symbols with no expiries and sort by symbol
            all_expiries = {k: v for k, v in all_expiries.items() if v}
            
            self.logger.info(f"✅ Found expiries for {len(all_expiries)} symbols")
            return all_expiries
            
        except Exception as e:
            self.logger.error(f"❌ Error getting all expiries: {e}")
            return {}

    def get_expiry_dates(self, symbol: str) -> List[str]:
        """Get all expiry dates for a given symbol"""
        try:
            self._ensure_session()
            # Determine exchange
            exchange = self._get_exchange_for_symbol(symbol)
            
            # Get instruments
            instruments_df = self._get_instruments(exchange)
            
            if instruments_df.empty:
                return []
            
            # Filter by symbol and get unique expiry dates
            symbol_instruments = instruments_df[
                (instruments_df['name'] == symbol) & 
                (instruments_df['instrument_type'].isin(['CE', 'PE']))
            ]
            
            if symbol_instruments.empty:
                self.logger.warning(f"No option instruments found for {symbol}")
                return []
            
            # Get unique expiry dates and sort them
            if 'expiry' in symbol_instruments.columns:
                # Handle different date formats
                if pd.api.types.is_datetime64_any_dtype(symbol_instruments['expiry']):
                    expiry_dates = symbol_instruments['expiry'].dt.strftime('%Y-%m-%d').unique()
                else:
                    # Convert to datetime first if it's not already
                    symbol_instruments_copy = symbol_instruments.copy()
                    symbol_instruments_copy['expiry'] = pd.to_datetime(symbol_instruments_copy['expiry'])
                    expiry_dates = symbol_instruments_copy['expiry'].dt.strftime('%Y-%m-%d').unique()
            else:
                self.logger.warning(f"No expiry column found for {symbol}")
                return []
            expiry_dates = sorted(expiry_dates)
            
            self.logger.info(f"✅ Found {len(expiry_dates)} expiry dates for {symbol}")
            return expiry_dates
            
        except Exception as e:
            self.logger.error(f"❌ Error getting expiry dates for {symbol}: {e}")
            return []
    
    def _get_mcx_trading_symbol(self, symbol: str) -> str:
        """Get the correct MCX trading symbol for commodities"""
        try:
            # Get MCX instruments
            mcx_instruments = self._get_instruments("MCX")
            if mcx_instruments.empty:
                self.logger.warning("No MCX instruments available")
                return f"MCX:{symbol}"
            
            # Find the most relevant futures contract for the commodity
            # Look for the symbol in the name or tradingsymbol columns
            matching_instruments = mcx_instruments[
                (mcx_instruments['name'].str.contains(symbol, case=False, na=False)) |
                (mcx_instruments['tradingsymbol'].str.contains(symbol, case=False, na=False))
            ]
            
            if matching_instruments.empty:
                self.logger.warning(f"No MCX instruments found for {symbol}")
                # Try some common alternative names
                alternatives = {
                    'NATGASMINI': 'NATURALGAS',
                    'NATURALGAS': 'NATGAS',
                    'CRUDEOILM': 'CRUDEOIL'
                }
                if symbol in alternatives:
                    alt_symbol = alternatives[symbol]
                    matching_instruments = mcx_instruments[
                        (mcx_instruments['name'].str.contains(alt_symbol, case=False, na=False)) |
                        (mcx_instruments['tradingsymbol'].str.contains(alt_symbol, case=False, na=False))
                    ]
                
                if matching_instruments.empty:
                    return f"MCX:{symbol}"
            
            # Prefer futures contracts over options, and get the nearest expiry
            futures = matching_instruments[matching_instruments['instrument_type'] == 'FUT']
            if not futures.empty:
                # Prefer the nearest non-expired future; fallback to most recent past
                if 'expiry' in futures.columns:
                    futures_copy = futures.copy()
                    futures_copy['expiry_dt'] = pd.to_datetime(futures_copy['expiry'], errors='coerce')
                    today = datetime.now().date()
                    future_contracts = futures_copy[futures_copy['expiry_dt'].dt.date >= today]
                    if not future_contracts.empty:
                        nearest_future = future_contracts.sort_values('expiry_dt').iloc[0]
                    else:
                        # All contracts are expired; pick the latest expired to still get history/ltp
                        nearest_future = futures_copy.sort_values('expiry_dt').iloc[-1]
                    trading_symbol = f"MCX:{nearest_future['tradingsymbol']}"
                    self.logger.info(f"Found MCX futures symbol for {symbol}: {trading_symbol}")
                    return trading_symbol
                else:
                    # No expiry column, use first futures contract
                    first_future = futures.iloc[0]
                    trading_symbol = f"MCX:{first_future['tradingsymbol']}"
                    self.logger.info(f"Using first MCX futures symbol for {symbol}: {trading_symbol}")
                    return trading_symbol
            
            # If no futures found, use the first available instrument
            first_instrument = matching_instruments.iloc[0]
            trading_symbol = f"MCX:{first_instrument['tradingsymbol']}"
            self.logger.info(f"Using first available MCX symbol for {symbol}: {trading_symbol}")
            return trading_symbol
            
        except Exception as e:
            self.logger.error(f"Error finding MCX symbol for {symbol}: {e}")
            return f"MCX:{symbol}"
    
    def _get_exchange_for_symbol(self, symbol: str) -> str:
        """Determine the appropriate exchange for a given symbol"""
        # MCX Commodities
        mcx_commodities = {
            'COPPER', 'CRUDEOIL', 'CRUDEOILM', 'GOLD', 'GOLDM', 
            'NATGASMINI', 'NATURALGAS', 'SILVER', 'SILVERM', 'ZINC'
        }
        
        if symbol in mcx_commodities:
            return "MCX"
        elif symbol == "SENSEX":
            return "BFO"
        else:
            return "NFO"
    
    def get_spot_price(self, symbol: str) -> Dict[str, Any]:
        """Get current spot price for a symbol"""
        try:
            self._ensure_session()
            # Map symbol to trading symbol
            if symbol == "NIFTY":
                trading_symbol = "NSE:NIFTY 50"
            elif symbol == "BANKNIFTY":
                trading_symbol = "NSE:NIFTY BANK"
            elif symbol == "FINNIFTY":
                trading_symbol = "NSE:NIFTY FIN SERVICE"
            elif symbol == "MIDCPNIFTY":
                trading_symbol = "NSE:NIFTY MID SELECT"
            elif symbol == "SENSEX":
                trading_symbol = "BSE:SENSEX"
            # MCX Commodities - Use dynamic symbol lookup
            elif symbol in ['COPPER', 'CRUDEOIL', 'CRUDEOILM', 'GOLD', 'GOLDM', 
                           'NATGASMINI', 'NATURALGAS', 'SILVER', 'SILVERM', 'ZINC']:
                trading_symbol = self._get_mcx_trading_symbol(symbol)
            else:
                trading_symbol = f"NSE:{symbol}"
            
            # Check cache (1 second cache for quotes - real-time updates)
            cache_key = trading_symbol
            current_time = datetime.now()
            if (cache_key in self._quotes_cache and 
                cache_key in self._quotes_cache_time and
                (current_time - self._quotes_cache_time[cache_key]).seconds < 1):
                return self._quotes_cache[cache_key]
            
            # Fetch quote
            quote_data = self.kite.quote([trading_symbol])
            quote = quote_data[trading_symbol]
            
            # Calculate change and change percent more robustly
            current_price = quote['last_price']
            previous_close = quote['ohlc']['close']
            net_change = quote.get('net_change', current_price - previous_close)
            
            # If net_change is 0 but prices are different, calculate manually
            if net_change == 0 and current_price != previous_close:
                net_change = current_price - previous_close
            
            # Ensure we have valid previous close to avoid division by zero
            if previous_close > 0:
                change_percent = ((current_price - previous_close) / previous_close) * 100
            else:
                change_percent = 0.0
            
            result = {
                'symbol': symbol,
                'spot_price': current_price,
                'previous_close': previous_close,
                'change': net_change,
                'change_percent': change_percent,
                'volume': convert_abbreviated_to_exact(quote.get('volume', 0)),
                'timestamp': datetime.now().isoformat()
            }
            
            # Cache the result
            self._quotes_cache[cache_key] = result
            self._quotes_cache_time[cache_key] = current_time
            
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Error getting spot price for {symbol}: {e}")
            return {
                'symbol': symbol,
                'spot_price': 0,
                'previous_close': 0,
                'change': 0,
                'change_percent': 0,
                'volume': 0,
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            }
        except Exception as e:
            self.logger.error(f"❌ Error fetching spot price for {symbol}: {e}")
            return {
                'symbol': symbol,
                'spot_price': 0,
                'previous_close': 0,
                'change': 0,
                'change_percent': 0,
                'volume': 0,
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            }

    def get_recent_daily_history(self, symbol: str, days: int = 2) -> List[Dict[str, Any]]:
        """Fetch recent daily historical candles for a symbol (up to 'days').

        Resolves trading symbol similarly to get_spot_price, obtains instrument token
        from quote, then calls Kite historical_data API with interval 'day'.
        Handles weekends (fetches extra days and trims). Returns list of dicts
        sorted ascending by date with keys: date, open, high, low, close, volume.
        """
        try:
            self._ensure_session()
            # Serve from cache if fresh
            try:
                cache_key = (symbol, int(max(1, min(days, 10))))
            except Exception:
                cache_key = (symbol, 2)
            cached = self._daily_history_cache.get(cache_key)
            if cached:
                fetched_at = cached.get('fetched_at')
                # TTL: 300 seconds; previous day won't change intraday, today's open fixed
                if fetched_at and (datetime.now() - fetched_at).total_seconds() < 300:
                    return cached.get('data', [])
            days = max(1, min(days, 10))
            # Reuse trading symbol resolution logic
            if symbol == "NIFTY":
                trading_symbol = "NSE:NIFTY 50"
            elif symbol == "BANKNIFTY":
                trading_symbol = "NSE:NIFTY BANK"
            elif symbol == "FINNIFTY":
                trading_symbol = "NSE:NIFTY FIN SERVICE"
            elif symbol == "MIDCPNIFTY":
                trading_symbol = "NSE:NIFTY MID SELECT"
            elif symbol == "SENSEX":
                trading_symbol = "BSE:SENSEX"
            elif symbol in ['COPPER', 'CRUDEOIL', 'CRUDEOILM', 'GOLD', 'GOLDM', 'NATGASMINI', 'NATURALGAS', 'SILVER', 'SILVERM', 'ZINC']:
                trading_symbol = self._get_mcx_trading_symbol(symbol)
            else:
                trading_symbol = f"NSE:{symbol}"

            quote_data = self.kite.quote([trading_symbol])
            quote = quote_data[trading_symbol]
            instrument_token = quote.get('instrument_token')
            if not instrument_token:
                raise ValueError(f"No instrument token for {symbol}")

            # Fetch a wider window to account for weekends/holidays
            fetch_from = (datetime.now() - timedelta(days=days + 7)).date()
            fetch_to = datetime.now().date()

            candles = self.kite.historical_data(instrument_token, fetch_from, fetch_to, 'day')
            # candles: list of dict date, open, high, low, close, volume, oi
            # Filter and take the last 'days'
            candles_sorted = sorted(candles, key=lambda c: c['date'])
            recent = candles_sorted[-days:]
            result = []
            for c in recent:
                result.append({
                    'date': c['date'].isoformat() if hasattr(c['date'], 'isoformat') else str(c['date']),
                    'open': c['open'],
                    'high': c['high'],
                    'low': c['low'],
                    'close': c['close'],
                    'volume': c.get('volume', 0)
                })
            # Save to cache
            self._daily_history_cache[cache_key] = {
                'data': result,
                'fetched_at': datetime.now()
            }
            return result
        except Exception as e:
            self.logger.error(f"❌ Error fetching recent daily history for {symbol}: {e}")
            return []

    def get_underlying_intraday_ohlc(self, symbol: str) -> Dict[str, Any]:
        """Fetch current-day intraday OHLC for an underlying using minute candles.

        Resolves the appropriate trading symbol and instrument token, fetches minute
        candles for today, and aggregates open/high/low/close and total volume.
        """
        try:
            self._ensure_session()
            # Resolve trading symbol (reuse logic from get_spot_price)
            if symbol == "NIFTY":
                trading_symbol = "NSE:NIFTY 50"
            elif symbol == "BANKNIFTY":
                trading_symbol = "NSE:NIFTY BANK"
            elif symbol == "FINNIFTY":
                trading_symbol = "NSE:NIFTY FIN SERVICE"
            elif symbol == "MIDCPNIFTY":
                trading_symbol = "NSE:NIFTY MID SELECT"
            elif symbol == "SENSEX":
                trading_symbol = "BSE:SENSEX"
            elif symbol in ['COPPER', 'CRUDEOIL', 'CRUDEOILM', 'GOLD', 'GOLDM', 'NATGASMINI', 'NATURALGAS', 'SILVER', 'SILVERM', 'ZINC']:
                trading_symbol = self._get_mcx_trading_symbol(symbol)
            else:
                trading_symbol = f"NSE:{symbol}"

            quote_data = self.kite.quote([trading_symbol])
            quote = quote_data[trading_symbol]
            token = quote.get('instrument_token')
            if not token:
                raise ValueError(f"No instrument token for {symbol}")

            # Fetch minute candles today
            now = datetime.now()
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            candles = self.kite.historical_data(token, start, now, 'minute')
            if not candles:
                # Fallback: use quote ohlc
                o = (quote.get('ohlc') or {}).get('open')
                h = (quote.get('ohlc') or {}).get('high')
                l = (quote.get('ohlc') or {}).get('low')
                c = quote.get('last_price')
                return {
                    'open': o or c,
                    'high': h or c,
                    'low': l or c,
                    'close': c,
                    'volume': quote.get('volume', 0),
                    'fetched_at': now
                }

            # Filter to today and aggregate
            today = now.date()
            today_candles = [c for c in candles if getattr(c.get('date'), 'date', lambda: None)() == today]
            if not today_candles:
                today_candles = candles  # best effort if API returns only today anyway

            first = today_candles[0]
            last = today_candles[-1]
            high = max(c['high'] for c in today_candles)
            low = min(c['low'] for c in today_candles)
            tot_vol = sum(c.get('volume', 0) or 0 for c in today_candles)
            return {
                'open': first.get('open'),
                'high': high,
                'low': low,
                'close': last.get('close'),
                'volume': tot_vol,
                'fetched_at': now
            }
        except Exception as e:
            self.logger.error(f"❌ Error fetching intraday OHLC for {symbol}: {e}")
            return {}

    # ------------------ Minute candles helper for underlying ------------------ #
    def get_recent_minute_candles(self, symbol: str, minutes: int = 5) -> List[Dict[str, Any]]:
        """Fetch recent N minutes candles for an underlying symbol.

        Returns a list of candle dicts with at least keys: date, open, high, low, close, volume.
        If the API returns more than needed, the last `minutes` candles for today are returned.
        """
        try:
            self._ensure_session()
            # Resolve trading symbol and token
            mapping = self._resolve_symbol_to_instrument(symbol)
            if not mapping:
                return []
            token = mapping['instrument_token']

            now = datetime.now()
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            candles = self.kite.historical_data(token, start, now, 'minute')
            if not candles:
                return []

            # Keep only today's candles
            today = now.date()
            today_candles = [c for c in candles if getattr(c.get('date'), 'date', lambda: None)() == today]
            if not today_candles:
                today_candles = candles

            return today_candles[-minutes:]
        except Exception as e:
            self.logger.error(f"❌ Error fetching recent minute candles for {symbol}: {e}")
            return []

    # ------------------ Option contract previous-day OHLC helpers ------------------ #
    def _get_previous_trading_day(self) -> date:
        """Return the previous trading day date (simple weekday rollback).

        NOTE: Does not account for exchange holidays; for a holiday the function will
        return the last weekday which may still have no candle; higher-level logic
        will then fallback to the most recent available candle prior to that date.
        """
        d = datetime.now().date() - timedelta(days=1)
        # Weekend handling (Sat/Sun)
        while d.weekday() >= 5:  # 5=Sat,6=Sun
            d -= timedelta(days=1)
        return d

    def get_previous_day_option_ohlc(self, tokens: List[int], max_fetch: int = 60) -> Dict[int, Dict[str, Any]]:
        """Fetch previous-day daily OHLC for each option instrument token.

        Uses Kite historical_data per token (no bulk endpoint exists). Implements
        per-day caching to avoid repeated calls during the trading session.
        Returns mapping: token -> {'prev_high','prev_low','prev_close','prev_open'}.
        If previous trading day candle absent (holiday), falls back to the most
        recent earlier daily candle available in the fetched range.
        """
        result: Dict[int, Dict[str, Any]] = {}
        if not tokens:
            return result
        self._ensure_session()

        prev_trading_day = self._get_previous_trading_day()
        # We will look back up to 7 calendar days to accommodate holidays/weekends
        fetch_from = prev_trading_day - timedelta(days=7)
        fetch_to = datetime.now().date()

        now = datetime.now()
        # Honor cooldown if set
        if self._rate_limit_prevday_cooldown_until and now < self._rate_limit_prevday_cooldown_until:
            self.logger.info(f"Skipping prev-day OHLC fetch due to cooldown until {self._rate_limit_prevday_cooldown_until}")
            return result

        fetched_count = 0
        for token in tokens:
            # Serve from cache if available for the current prev_trading_day
            cache_rec = self._option_prev_day_cache.get(token)
            if cache_rec and cache_rec.get('for_day') == prev_trading_day:
                result[token] = cache_rec
                continue
            if fetched_count >= max_fetch:
                # Defer remaining tokens to future calls; cache will progressively fill
                continue
            try:
                candles = self.kite.historical_data(token, fetch_from, fetch_to, 'day')
                if not candles:
                    continue
                # Sort ascending by date
                candles_sorted = sorted(candles, key=lambda c: c['date'])
                # Find candle matching prev_trading_day; else take last strictly before today
                chosen = None
                for c in reversed(candles_sorted):
                    c_date = c['date'].date() if hasattr(c['date'], 'date') else c['date']
                    if c_date == prev_trading_day:
                        chosen = c
                        break
                    # If we passed earlier than prev_trading_day and nothing selected, fallback to first earlier
                    if c_date < prev_trading_day and chosen is None:
                        chosen = c
                        break
                if chosen:
                    rec = {
                        'for_day': prev_trading_day,
                        'prev_open': chosen.get('open'),
                        'prev_high': chosen.get('high'),
                        'prev_low': chosen.get('low'),
                        'prev_close': chosen.get('close')
                    }
                    self._option_prev_day_cache[token] = rec
                    self._persist_prevday_record(token, rec)
                    result[token] = rec
                    fetched_count += 1
            except Exception as e:
                msg = str(e)
                if 'Too many requests' in msg:
                    # Set cooldown and stop batch
                    self._rate_limit_prevday_cooldown_until = now + timedelta(seconds=180)
                    self.logger.warning(f"Prev-day OHLC rate-limited; cooling down until {self._rate_limit_prevday_cooldown_until}")
                    break
                else:
                    self.logger.warning(f"Prev-day option OHLC fetch failed for token {token}: {e}")
                    continue
        return result

    # -------- Prev-day cache background warming (speeds up first UI paint) -------- #
    def _prevday_cache_coverage(self, tokens: List[int]) -> float:
        """Return fraction of tokens cached for the current previous trading day."""
        if not tokens:
            return 1.0
        prev_trading_day = self._get_previous_trading_day()
        covered = 0
        for t in tokens:
            rec = self._option_prev_day_cache.get(int(t))
            if rec and rec.get('for_day') == prev_trading_day:
                covered += 1
        return covered / max(1, len(tokens))

    def _prevday_cache_file(self, day: date) -> str:
        return os.path.join(self._prevday_cache_dir, f"prevday_{day.isoformat()}.json")

    def _load_prevday_cache_for_today(self):
        """Load today's prev-day cache from disk into memory to speed startup."""
        try:
            d = self._get_previous_trading_day()
            path = self._prevday_cache_file(d)
            if not os.path.exists(path):
                return
            with open(path, 'r') as f:
                data = json.load(f)
            # JSON keys are strings; convert to int
            for k, v in data.items():
                try:
                    t = int(k)
                except Exception:
                    continue
                if isinstance(v, dict):
                    v['for_day'] = d
                    self._option_prev_day_cache[t] = v
        except Exception:
            # Non-critical: ignore
            return

    def _persist_prevday_record(self, token: int, rec: Dict[str, Any]):
        """Persist a single token record to disk (thread-safe)."""
        try:
            d = rec.get('for_day') or self._get_previous_trading_day()
            path = self._prevday_cache_file(d)
            with self._prevday_cache_lock:
                current: Dict[str, Any] = {}
                if os.path.exists(path):
                    try:
                        with open(path, 'r') as f:
                            current = json.load(f) or {}
                    except Exception:
                        current = {}
                current[str(int(token))] = {
                    'prev_open': rec.get('prev_open'),
                    'prev_high': rec.get('prev_high'),
                    'prev_low': rec.get('prev_low'),
                    'prev_close': rec.get('prev_close'),
                }
                tmp_path = path + '.tmp'
                with open(tmp_path, 'w') as f:
                    json.dump(current, f)
                os.replace(tmp_path, path)
        except Exception:
            # Non-critical: ignore
            return

    def _warm_prev_day_cache_worker(self, job_key: str, tokens: List[int]):
        """Background worker that progressively fills prev-day cache for tokens.

        Respects rate-limit cooldowns and sleeps between calls to avoid bursts.
        """
        try:
            # Closest-to-ATM ordering should already be passed in
            prev_trading_day = self._get_previous_trading_day()
            # Burst pacing: do a few calls, then short sleep
            per_call_sleep = 0.01
            calls_since_sleep = 0
            for token in tokens:
                # Stop if job was cleared
                job_meta = self._prevday_warm_jobs.get(job_key)
                if not job_meta or not job_meta.get('running'):
                    break
                # Skip if cached for the required day
                cached = self._option_prev_day_cache.get(int(token))
                if cached and cached.get('for_day') == prev_trading_day:
                    continue
                # Honor global cooldown
                if self._rate_limit_prevday_cooldown_until and datetime.now() < self._rate_limit_prevday_cooldown_until:
                    # Sleep until cooldown expires
                    sleep_for = max(1, int((self._rate_limit_prevday_cooldown_until - datetime.now()).total_seconds()))
                    time.sleep(sleep_for)
                try:
                    candles = self.kite.historical_data(int(token), prev_trading_day - timedelta(days=7), datetime.now().date(), 'day')
                    if candles:
                        candles_sorted = sorted(candles, key=lambda c: c['date'])
                        chosen = None
                        for c in reversed(candles_sorted):
                            c_date = c['date'].date() if hasattr(c['date'], 'date') else c['date']
                            if c_date == prev_trading_day:
                                chosen = c
                                break
                            if c_date < prev_trading_day and chosen is None:
                                chosen = c
                                break
                        if chosen:
                            rec = {
                                'for_day': prev_trading_day,
                                'prev_open': chosen.get('open'),
                                'prev_high': chosen.get('high'),
                                'prev_low': chosen.get('low'),
                                'prev_close': chosen.get('close'),
                            }
                            self._option_prev_day_cache[int(token)] = rec
                            self._persist_prevday_record(int(token), rec)
                    calls_since_sleep += 1
                    if calls_since_sleep % 15 == 0:
                        time.sleep(0.2)
                    else:
                        time.sleep(per_call_sleep)
                except Exception as e:
                    msg = str(e)
                    if 'Too many requests' in msg:
                        # Back off more aggressively
                        self._rate_limit_prevday_cooldown_until = datetime.now() + timedelta(seconds=180)
                        # Sleep a bit before retrying next token
                        time.sleep(5)
                    else:
                        # Minor error, proceed
                        time.sleep(per_call_sleep)
        finally:
            # Mark job complete
            job_meta = self._prevday_warm_jobs.get(job_key)
            if job_meta:
                job_meta['running'] = False

    def _ensure_prevday_warm(self, symbol: str, expiry: str, ordered_tokens: List[int]):
        """Kick off a background warmer if cache coverage is low for these tokens."""
        try:
            coverage = self._prevday_cache_coverage(ordered_tokens)
            # Start warmer if less than 70% covered
            if coverage >= 0.7 or not ordered_tokens:
                return
            # Launch limited concurrency (3 shards) to speed warm-up without hammering
            def shard(lst: List[int], parts: int) -> List[List[int]]:
                if parts <= 1:
                    return [list(lst)]
                shards: List[List[int]] = [[] for _ in range(parts)]
                for idx, val in enumerate(lst):
                    shards[idx % parts].append(val)
                return shards
            parts = 3
            shards = shard(ordered_tokens, parts)
            for i, shard_tokens in enumerate(shards):
                if not shard_tokens:
                    continue
                job_key = f"{symbol}:{expiry or 'nearest'}:{len(ordered_tokens)}#{i}"
                job = self._prevday_warm_jobs.get(job_key)
                if job and job.get('running'):
                    continue
                self._prevday_warm_jobs[job_key] = {'running': True, 'started_at': datetime.now()}
                t = threading.Thread(target=self._warm_prev_day_cache_worker, args=(job_key, list(shard_tokens)), daemon=True)
                t.start()
        except Exception:
            # Fail-safe: never block the main request path
            return
    
    # ------------------ Current day (true) intraday OHLC helpers ------------------ #
    def get_current_day_option_ohlc(self, tokens: List[int], max_age_sec: int = 60) -> Dict[int, Dict[str, Any]]:
        """Return current-day (since market open) OHLC for each option token using minute candles.

        Why: Existing logic initialized session OHLC from the first seen LTP, producing open/high/low=close
        when the service starts mid-session. This method reconstructs the true intraday O/H/L/C by querying
        historical minute data from market open (09:15) until now.

        Performance / Rate-limit note: Kite historical_data is a per-token REST call. Calling this for ALL
        strikes (hundreds) every refresh may exceed rate limits and slow responses. We therefore:
          * Cache per token for `max_age_sec` seconds (default 60)
          * Short-circuit entirely if token count is very large (> 400) to avoid overload (returns empty dict)
        Adjust these heuristics as needed. Consider migrating to WebSocket tick aggregation for scale.
        """
        result: Dict[int, Dict[str, Any]] = {}
        if not tokens:
            return result
        self._ensure_session()
        now = datetime.now()
        # Honor cooldown if we recently hit rate limit
        if self._rate_limit_intraday_cooldown_until and now < self._rate_limit_intraday_cooldown_until:
            self.logger.info(f"Skipping intraday OHLC fetch due to cooldown until {self._rate_limit_intraday_cooldown_until}")
            return result
        # If before market open, nothing to do
        market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
        if now < market_open:
            return result
        # Safety guard to avoid excessive API calls
        if len(tokens) > 400:
            self.logger.warning(f"Skipping intraday OHLC reconstruction for {len(tokens)} tokens to avoid rate limits")
            return result
        for token in tokens:
            cache_rec = self._option_today_cache.get(token)
            if cache_rec and (now - cache_rec.get('fetched_at', now)).seconds < max_age_sec and cache_rec.get('day') == now.date():
                result[token] = cache_rec
                continue
            try:
                # Fetch minute candles from market open to now
                candles = self.kite.historical_data(token, market_open, now, 'minute')
                if not candles:
                    continue
                first = candles[0]
                last = candles[-1]
                high = max(c['high'] for c in candles)
                low = min(c['low'] for c in candles)
                rec = {
                    'day': now.date(),
                    'open': first.get('open'),
                    'high': high,
                    'low': low,
                    'close': last.get('close'),
                    'fetched_at': now
                }
                self._option_today_cache[token] = rec
                result[token] = rec
            except Exception as e:
                msg = str(e)
                if 'Too many requests' in msg:
                    # Set cooldown and stop this batch
                    self._rate_limit_intraday_cooldown_until = now + timedelta(seconds=90)
                    self.logger.warning(f"Intraday OHLC rate-limited; cooling down until {self._rate_limit_intraday_cooldown_until}")
                    break
                else:
                    self.logger.warning(f"Intraday OHLC fetch failed for token {token}: {e}")
                continue
        return result
                
    def get_option_chain(self, symbol: str, expiry: str = None, strike_range: int = None, include_all_strikes: bool = True) -> Dict[str, Any]:
        """Get complete option chain for a symbol and expiry - INCLUDES ALL STRIKES by default

        Resiliency improvements:
        - Robust expiry parsing across mixed dtypes
        - Defensive batching for quotes with rate-limit handling
        - Guard calculations when strikes are empty
        """
        try:
            self._ensure_session()
            # Determine exchange
            exchange = self._get_exchange_for_symbol(symbol)
            
            # Get instruments
            instruments_df = self._get_instruments(exchange)
            
            if instruments_df.empty:
                raise ValueError(f"No instruments found for exchange {exchange}")
            
            # Filter option instruments for the symbol
            option_instruments = instruments_df[
                (instruments_df['name'] == symbol) & 
                (instruments_df['instrument_type'].isin(['CE', 'PE']))
            ].copy()
            
            if option_instruments.empty:
                raise ValueError(f"No option instruments found for {symbol}")
            
            # Filter by expiry if specified; normalize expiry column to datetime for reliable comparisons
            if 'expiry' not in option_instruments.columns:
                raise ValueError("Instruments do not contain an 'expiry' column")
            normalized = option_instruments.copy()
            try:
                normalized['expiry'] = pd.to_datetime(normalized['expiry'], errors='coerce')
            except Exception:
                # If conversion fails, drop rows without parseable expiry
                normalized['expiry'] = pd.to_datetime(normalized['expiry'].astype(str), errors='coerce')
            normalized = normalized.dropna(subset=['expiry'])
            if normalized.empty:
                raise ValueError("No instruments with a valid expiry date available")

            if expiry:
                expiry_date = pd.to_datetime(expiry).normalize()
                option_instruments = normalized[normalized['expiry'].dt.normalize() == expiry_date]
            else:
                # Use nearest/earliest expiry available
                min_exp = normalized['expiry'].min()
                option_instruments = normalized[normalized['expiry'] == min_exp]
                expiry = min_exp.strftime('%Y-%m-%d')
            
            if option_instruments.empty:
                raise ValueError(f"No option instruments found for {symbol} with expiry {expiry}")
            
            # Get spot price
            spot_data = self.get_spot_price(symbol)
            spot_price = spot_data['spot_price']
            
            # Get ALL strikes (no filtering by default)
            all_strikes = sorted(option_instruments['strike'].unique())
            
            # Apply strike range filter only if explicitly requested and include_all_strikes is False
            if strike_range and not include_all_strikes:
                atm_strike = min(all_strikes, key=lambda x: abs(x - spot_price))
                strike_interval = 50 if symbol in ['NIFTY', 'BANKNIFTY'] else 100
                
                min_strike = atm_strike - (strike_range * strike_interval)
                max_strike = atm_strike + (strike_range * strike_interval)
                
                option_instruments = option_instruments[
                    (option_instruments['strike'] >= min_strike) &
                    (option_instruments['strike'] <= max_strike)
                ]
                
                self.logger.info(f"Applied strike range filter: {min_strike} to {max_strike}")
            else:
                self.logger.info(f"Including ALL {len(all_strikes)} strikes for {symbol}")
            
            # Get all instrument tokens
            instrument_tokens = option_instruments['instrument_token'].dropna().astype(int).tolist()
            if not instrument_tokens:
                raise ValueError("No instrument tokens available after filtering")

            self.logger.info(f"Fetching quotes for {len(instrument_tokens)} option instruments...")

            # Fetch quotes in batches (Kite API limit: 500 per request); add small delay and error handling
            batch_size = 400
            all_quotes: Dict[str, Any] = {}
            for i in range(0, len(instrument_tokens), batch_size):
                batch_tokens = instrument_tokens[i:i + batch_size]
                try:
                    batch_quotes = self.kite.quote(batch_tokens)
                    if isinstance(batch_quotes, dict):
                        all_quotes.update(batch_quotes)
                    else:
                        self.logger.warning(f"Unexpected quotes response type: {type(batch_quotes)} for batch starting {i}")
                except Exception as e:
                    msg = str(e)
                    if 'Too many requests' in msg or '429' in msg:
                        self.logger.warning("Rate limited while fetching quotes; inserting short cooldown and continuing")
                        time.sleep(1.0)
                        try:
                            batch_quotes = self.kite.quote(batch_tokens)
                            if isinstance(batch_quotes, dict):
                                all_quotes.update(batch_quotes)
                        except Exception as e2:
                            self.logger.error(f"Quote batch failed after retry: {e2}")
                    else:
                        self.logger.error(f"Quote batch fetch failed: {e}")
                # polite pacing
                time.sleep(0.15)
            
            # Process option chain data
            option_chain_data = []
            # Ensure we have a usable strikes list
            try:
                strikes = sorted([float(s) for s in option_instruments['strike'].dropna().unique().tolist()])
            except Exception:
                strikes = []
            if not strikes:
                raise ValueError("No strikes available for the selected expiry")

            # Gather all CE/PE instrument tokens to prefetch previous-day per-option OHLC
            ce_tokens = option_instruments[option_instruments['instrument_type'] == 'CE']['instrument_token'].tolist()
            pe_tokens = option_instruments[option_instruments['instrument_type'] == 'PE']['instrument_token'].tolist()
            all_tokens = list(set(ce_tokens + pe_tokens))
            # To avoid rate limits, fetch prev-day candles only for the most relevant strikes (closest to ATM)
            # Build token->strike map
            token_strike_map = {int(row['instrument_token']): float(row['strike']) for _, row in option_instruments[['instrument_token','strike']].iterrows()}
            # Sort tokens by distance to spot
            sorted_tokens = sorted(all_tokens, key=lambda t: abs(token_strike_map.get(int(t), 0) - spot_price))
            # Progressive fetch across all tokens with per-call cap; cache fills over time
            # Start a background warm-up so values fill quickly on subsequent refreshes
            self._ensure_prevday_warm(symbol, expiry, [int(t) for t in sorted_tokens])
            # Fetch a larger batch synchronously on this call to improve first paint
            # Fetch a large batch synchronously to populate previous-day OHLC across most strikes
            try:
                total_tokens = len(sorted_tokens)
            except Exception:
                total_tokens = 0
            prev_fetch_cap = 450 if total_tokens >= 450 else total_tokens
            prev_day_map = self.get_previous_day_option_ohlc([int(t) for t in sorted_tokens], max_fetch=prev_fetch_cap)
            # True intraday current-day OHLC (may be partial). Limit to most relevant tokens near ATM to avoid rate limits.
            sorted_today_tokens = sorted(all_tokens, key=lambda t: abs(token_strike_map.get(int(t), 0) - spot_price))
            # Increase coverage to improve intraday OHLC availability while staying within limits
            MAX_TODAY_TOKENS = 150
            prioritized_today_tokens = [int(t) for t in sorted_today_tokens[:MAX_TODAY_TOKENS]]
            if len(all_tokens) > MAX_TODAY_TOKENS:
                self.logger.warning(f"Intraday OHLC limited to {MAX_TODAY_TOKENS}/{len(all_tokens)} tokens; remaining will use session/quote fallbacks")
            # True intraday current-day OHLC (may be partial).
            today_intraday_map = self.get_current_day_option_ohlc(prioritized_today_tokens, max_age_sec=180)
            # No underlying fallback for previous day to avoid incorrect duplication
            
            for strike in strikes:
                ce_data = option_instruments[
                    (option_instruments['strike'] == strike) & 
                    (option_instruments['instrument_type'] == 'CE')
                ]
                pe_data = option_instruments[
                    (option_instruments['strike'] == strike) & 
                    (option_instruments['instrument_type'] == 'PE')
                ]
                
                row = {'strike_price': strike}
                
                # Process CE data
                if not ce_data.empty:
                    ce_token = ce_data.iloc[0]['instrument_token']
                    # Support both int and string keys returned by kite.quote
                    ce_quote = all_quotes.get(ce_token) or all_quotes.get(str(ce_token)) or {}
                    
                    ce_ltp = ce_quote.get('last_price', 0)
                    self._update_session_ohlc(int(ce_token), ce_ltp)
                    ce_session = self._session_ohlc.get(int(ce_token), {})
                    ce_ohlc = ce_quote.get('ohlc', {}) or {}
                    # Prefer reconstructed intraday OHLC; then quote OHLC; then session aggregates; never keep zeros.
                    ce_intraday = today_intraday_map.get(int(ce_token), {})
                    ce_open = self._first_positive(ce_intraday.get('open'), ce_ohlc.get('open'), ce_session.get('open'), ce_ltp)
                    ce_high = self._first_positive(ce_intraday.get('high'), ce_ohlc.get('high'), ce_session.get('high'), ce_open, ce_ltp)
                    ce_low = self._first_positive(ce_intraday.get('low'), ce_ohlc.get('low'), ce_session.get('low'), ce_open, ce_ltp)
                    ce_close = self._first_positive(ce_intraday.get('close'), ce_ohlc.get('close'), ce_session.get('close'), ce_ltp)
                    ce_volume = convert_abbreviated_to_exact(ce_quote.get('volume', 0))
                    ce_oi = convert_abbreviated_to_exact(ce_quote.get('oi', 0))
                    ce_bid = ce_quote.get('depth', {}).get('buy', [{}])[0].get('price', 0)
                    ce_ask = ce_quote.get('depth', {}).get('sell', [{}])[0].get('price', 0)
                    ce_bid_qty = ce_quote.get('depth', {}).get('buy', [{}])[0].get('quantity', 0)
                    ce_ask_qty = ce_quote.get('depth', {}).get('sell', [{}])[0].get('quantity', 0)
                    
                    # Calculate Greeks for CE
                    time_to_expiry = self.greeks_calculator.calculate_time_to_expiry(expiry)
                    implied_vol = self.greeks_calculator.calculate_implied_volatility_estimate(
                        ce_ltp, spot_price, strike, time_to_expiry, 0.05, 'CE'
                    )
                    
                    ce_delta = self.greeks_calculator.calculate_delta(
                        spot_price, strike, time_to_expiry, 0.05, implied_vol, 'CE'
                    )
                    ce_gamma = self.greeks_calculator.calculate_gamma(
                        spot_price, strike, time_to_expiry, 0.05, implied_vol
                    )
                    ce_theta = self.greeks_calculator.calculate_theta(
                        spot_price, strike, time_to_expiry, 0.05, implied_vol, 'CE'
                    )
                    ce_vega = self.greeks_calculator.calculate_vega(
                        spot_price, strike, time_to_expiry, 0.05, implied_vol
                    )
                    ce_rho = self.greeks_calculator.calculate_rho(
                        spot_price, strike, time_to_expiry, 0.05, implied_vol, 'CE'
                    )
                    
                    # Calculate analysis fields for CE
                    ce_analysis = self._calculate_analysis_fields(
                        'CE', ce_ltp, spot_price, strike, ce_delta, ce_gamma, 
                        ce_theta, ce_vega, time_to_expiry
                    )
                    
                    prev_rec = prev_day_map.get(int(ce_token), {})
                    # Only use true per-option previous-day values; if missing, leave undefined to avoid synthetic values
                    ce_prev_open = prev_rec.get('prev_open') if prev_rec.get('prev_open') is not None else None
                    ce_prev_high = prev_rec.get('prev_high') if prev_rec.get('prev_high') is not None else None
                    ce_prev_low = prev_rec.get('prev_low') if prev_rec.get('prev_low') is not None else None
                    # Fallback prev_close to quote's previous close when historical access is unavailable
                    ce_prev_close = prev_rec.get('prev_close') if prev_rec.get('prev_close') is not None else (ce_quote.get('ohlc', {}) or {}).get('close')
                    row.update({
                        'ce_ltp': ce_ltp,
                        'ce_open': ce_open,
                        'ce_high': ce_high,
                        'ce_low': ce_low,
                        'ce_close': ce_close if ce_close is not None else ce_ltp,
                        'ce_prev_open': ce_prev_open,
                        'ce_prev_high': ce_prev_high,
                        'ce_prev_low': ce_prev_low,
                        'ce_prev_close': ce_prev_close,
                        'ce_volume': ce_volume,
                        'ce_oi': ce_oi,
                        'ce_bid': ce_bid,
                        'ce_ask': ce_ask,
                        'ce_bid_qty': ce_bid_qty,
                        'ce_ask_qty': ce_ask_qty,
                        'ce_iv': implied_vol * 100,  # Convert to percentage
                        'ce_delta': ce_delta,
                        'ce_gamma': ce_gamma,
                        'ce_theta': ce_theta,
                        'ce_vega': ce_vega,
                        'ce_rho': ce_rho,
                        'ce_change': ce_quote.get('net_change', 0),
                        'ce_change_percent': ce_quote.get('net_change_percent', 0),
                        # Add analysis fields
                        'ce_intrinsic': ce_analysis['intrinsic'],
                        'ce_time_val': ce_analysis['time_val'],
                        'ce_buy_percent': ce_analysis['buy_percent'],
                        'ce_sell_percent': ce_analysis['sell_percent'],
                        'ce_tp1': ce_analysis['tp1'],
                        'ce_tp2': ce_analysis['tp2'],
                        'ce_tp3': ce_analysis['tp3'],
                        'ce_stop_loss': ce_analysis['stop_loss'],
                        'ce_signal_type': ce_analysis['signal_type'],
                        'ce_signal_strength': ce_analysis['signal_strength'],
                        'ce_signal_quality': ce_analysis['signal_quality'],
                        'ce_signal_confidence': ce_analysis['signal_confidence']
                    })
                else:
                    row.update({
                        'ce_ltp': 0, 'ce_volume': 0, 'ce_oi': 0, 'ce_bid': 0, 'ce_ask': 0,
                        'ce_bid_qty': 0, 'ce_ask_qty': 0,
                        'ce_iv': 0, 'ce_delta': 0, 'ce_gamma': 0, 'ce_theta': 0, 'ce_vega': 0, 'ce_rho': 0,
                        'ce_change': 0, 'ce_change_percent': 0,
                        'ce_intrinsic': 0, 'ce_time_val': 0, 'ce_buy_percent': 0, 'ce_sell_percent': 0,
                        'ce_tp1': 0, 'ce_tp2': 0, 'ce_tp3': 0, 'ce_stop_loss': 0,
                        'ce_signal_type': 'HOLD', 'ce_signal_strength': 3, 'ce_signal_quality': 'moderate', 'ce_signal_confidence': 'medium'
                    })
                
                # Process PE data
                if not pe_data.empty:
                    pe_token = pe_data.iloc[0]['instrument_token']
                    pe_quote = all_quotes.get(pe_token) or all_quotes.get(str(pe_token)) or {}
                    
                    pe_ltp = pe_quote.get('last_price', 0)
                    self._update_session_ohlc(int(pe_token), pe_ltp)
                    pe_session = self._session_ohlc.get(int(pe_token), {})
                    pe_volume = convert_abbreviated_to_exact(pe_quote.get('volume', 0))
                    pe_oi = convert_abbreviated_to_exact(pe_quote.get('oi', 0))
                    pe_bid = pe_quote.get('depth', {}).get('buy', [{}])[0].get('price', 0)
                    pe_ask = pe_quote.get('depth', {}).get('sell', [{}])[0].get('price', 0)
                    pe_bid_qty = pe_quote.get('depth', {}).get('buy', [{}])[0].get('quantity', 0)
                    pe_ask_qty = pe_quote.get('depth', {}).get('sell', [{}])[0].get('quantity', 0)
                    
                    # Calculate Greeks for PE
                    time_to_expiry = self.greeks_calculator.calculate_time_to_expiry(expiry)
                    implied_vol = self.greeks_calculator.calculate_implied_volatility_estimate(
                        pe_ltp, spot_price, strike, time_to_expiry, 0.05, 'PE'
                    )
                    
                    pe_delta = self.greeks_calculator.calculate_delta(
                        spot_price, strike, time_to_expiry, 0.05, implied_vol, 'PE'
                    )
                    pe_gamma = self.greeks_calculator.calculate_gamma(
                        spot_price, strike, time_to_expiry, 0.05, implied_vol
                    )
                    pe_theta = self.greeks_calculator.calculate_theta(
                        spot_price, strike, time_to_expiry, 0.05, implied_vol, 'PE'
                    )
                    pe_vega = self.greeks_calculator.calculate_vega(
                        spot_price, strike, time_to_expiry, 0.05, implied_vol
                    )
                    pe_rho = self.greeks_calculator.calculate_rho(
                        spot_price, strike, time_to_expiry, 0.05, implied_vol, 'PE'
                    )
                    
                    # Calculate analysis fields for PE
                    pe_analysis = self._calculate_analysis_fields(
                        'PE', pe_ltp, spot_price, strike, pe_delta, pe_gamma, 
                        pe_theta, pe_vega, time_to_expiry
                    )
                    
                    pe_ohlc = pe_quote.get('ohlc', {}) or {}
                    prev_rec = prev_day_map.get(int(pe_token), {})
                    pe_intraday = today_intraday_map.get(int(pe_token), {})
                    # Only use true per-option previous-day values; if missing, leave undefined to avoid synthetic values
                    pe_prev_open = prev_rec.get('prev_open') if prev_rec.get('prev_open') is not None else None
                    pe_prev_high = prev_rec.get('prev_high') if prev_rec.get('prev_high') is not None else None
                    pe_prev_low = prev_rec.get('prev_low') if prev_rec.get('prev_low') is not None else None
                    pe_prev_close = prev_rec.get('prev_close') if prev_rec.get('prev_close') is not None else (pe_quote.get('ohlc', {}) or {}).get('close')
                    row.update({
                        'pe_ltp': pe_ltp,
                        'pe_open': self._first_positive(pe_intraday.get('open'), pe_session.get('open'), pe_ohlc.get('open'), pe_ltp),
                        'pe_high': self._first_positive(pe_intraday.get('high'), pe_session.get('high'), pe_ohlc.get('high'), pe_ltp),
                        'pe_low': self._first_positive(pe_intraday.get('low'), pe_session.get('low'), pe_ohlc.get('low'), pe_ltp),
                        'pe_close': self._first_positive(pe_intraday.get('close'), pe_session.get('close'), pe_ohlc.get('close'), pe_ltp),
                        'pe_prev_open': pe_prev_open,
                        'pe_prev_high': pe_prev_high,
                        'pe_prev_low': pe_prev_low,
                        'pe_prev_close': pe_prev_close,
                        'pe_volume': pe_volume,
                        'pe_oi': pe_oi,
                        'pe_bid': pe_bid,
                        'pe_ask': pe_ask,
                        'pe_bid_qty': pe_bid_qty,
                        'pe_ask_qty': pe_ask_qty,
                        'pe_iv': implied_vol * 100,  # Convert to percentage
                        'pe_delta': pe_delta,
                        'pe_gamma': pe_gamma,
                        'pe_theta': pe_theta,
                        'pe_vega': pe_vega,
                        'pe_rho': pe_rho,
                        'pe_change': pe_quote.get('net_change', 0),
                        'pe_change_percent': pe_quote.get('net_change_percent', 0),
                        # Add analysis fields
                        'pe_intrinsic': pe_analysis['intrinsic'],
                        'pe_time_val': pe_analysis['time_val'],
                        'pe_buy_percent': pe_analysis['buy_percent'],
                        'pe_sell_percent': pe_analysis['sell_percent'],
                        'pe_tp1': pe_analysis['tp1'],
                        'pe_tp2': pe_analysis['tp2'],
                        'pe_tp3': pe_analysis['tp3'],
                        'pe_stop_loss': pe_analysis['stop_loss'],
                        'pe_signal_type': pe_analysis['signal_type'],
                        'pe_signal_strength': pe_analysis['signal_strength'],
                        'pe_signal_quality': pe_analysis['signal_quality'],
                        'pe_signal_confidence': pe_analysis['signal_confidence']
                    })
                else:
                    row.update({
                        'pe_ltp': 0, 'pe_volume': 0, 'pe_oi': 0, 'pe_bid': 0, 'pe_ask': 0,
                        'pe_bid_qty': 0, 'pe_ask_qty': 0,
                        'pe_iv': 0, 'pe_delta': 0, 'pe_gamma': 0, 'pe_theta': 0, 'pe_vega': 0, 'pe_rho': 0,
                        'pe_change': 0, 'pe_change_percent': 0,
                        'pe_intrinsic': 0, 'pe_time_val': 0, 'pe_buy_percent': 0, 'pe_sell_percent': 0,
                        'pe_tp1': 0, 'pe_tp2': 0, 'pe_tp3': 0, 'pe_stop_loss': 0,
                        'pe_signal_type': 'HOLD', 'pe_signal_strength': 3, 'pe_signal_quality': 'moderate', 'pe_signal_confidence': 'medium'
                    })
                
                option_chain_data.append(row)
            
            # Calculate summary metrics
            total_ce_oi = sum(row['ce_oi'] for row in option_chain_data)
            total_pe_oi = sum(row['pe_oi'] for row in option_chain_data)
            total_ce_volume = sum(row['ce_volume'] for row in option_chain_data)
            total_pe_volume = sum(row['pe_volume'] for row in option_chain_data)
            
            pcr_oi = total_pe_oi / total_ce_oi if total_ce_oi > 0 else 0
            atm_strike = min(strikes, key=lambda x: abs(x - spot_price))
            
            # Calculate Max Pain (simplified)
            max_pain = self._calculate_max_pain(option_chain_data, strikes)
            
            result = {
                'symbol': symbol,
                'expiry': expiry,
                'spot_price': spot_price,
                'previous_close': spot_data['previous_close'],
                'change': spot_data['change'],
                'change_percent': spot_data['change_percent'],
                'atm_strike': atm_strike,
                'total_ce_oi': total_ce_oi,
                'total_pe_oi': total_pe_oi,
                'total_ce_volume': total_ce_volume,
                'total_pe_volume': total_pe_volume,
                'pcr_oi': pcr_oi,
                'max_pain': max_pain,
                'max_gain': atm_strike,  # Simplified
                'option_chain': option_chain_data,
                'timestamp': datetime.now().isoformat(),
                'data_source': 'kite_api'
            }
            
            self.logger.info(f"✅ Successfully fetched option chain for {symbol} {expiry} with {len(option_chain_data)} strikes")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Error fetching option chain for {symbol}: {e}")
            raise
    
    def _calculate_max_pain(self, option_chain_data: List[Dict], strikes: List[float]) -> float:
        """Calculate Max Pain strike"""
        try:
            max_pain_values = []
            
            for strike in strikes:
                total_pain = 0
                
                for row in option_chain_data:
                    row_strike = row['strike_price']
                    ce_oi = row['ce_oi']
                    pe_oi = row['pe_oi']
                    
                    # Calculate pain for CE options
                    if strike > row_strike:
                        total_pain += ce_oi * (strike - row_strike)
                    
                    # Calculate pain for PE options
                    if strike < row_strike:
                        total_pain += pe_oi * (row_strike - strike)
                
                max_pain_values.append((strike, total_pain))
            
            # Find strike with minimum pain
            max_pain_strike = min(max_pain_values, key=lambda x: x[1])[0]
            return max_pain_strike
            
        except Exception as e:
            self.logger.error(f"Error calculating max pain: {e}")
            return 0
    
    def get_dashboard_data(self, symbol: str, expiry: str = None) -> Dict[str, Any]:
        """Get dashboard data for a symbol"""
        try:
            option_chain_data = self.get_option_chain(symbol, expiry)
            
            # Extract dashboard metrics
            dashboard_data = {
                'symbol': symbol,
                'spot_price': option_chain_data['spot_price'],
                'change': option_chain_data['change'],
                'change_percent': option_chain_data['change_percent'],
                'total_ce_oi': option_chain_data['total_ce_oi'],
                'total_pe_oi': option_chain_data['total_pe_oi'],
                'total_ce_volume': option_chain_data['total_ce_volume'],
                'total_pe_volume': option_chain_data['total_pe_volume'],
                'pcr_oi': option_chain_data['pcr_oi'],
                'atm_strike': option_chain_data['atm_strike'],
                'max_pain': option_chain_data['max_pain'],
                'max_gain': option_chain_data['max_gain'],
                'timestamp': option_chain_data['timestamp']
            }
            
            return dashboard_data
            
        except Exception as e:
            self.logger.error(f"❌ Error getting dashboard data for {symbol}: {e}")
            raise
    
    def export_all_market_data(self, output_dir: str = "real_market_data_export") -> Dict[str, Any]:
        """Export ALL real market data to files - comprehensive data dump"""
        try:
            import os
            import json
            from datetime import date, datetime
            
            # Custom JSON encoder to handle date objects
            class DateTimeEncoder(json.JSONEncoder):
                def default(self, obj):
                    if isinstance(obj, (date, datetime)):
                        return obj.isoformat()
                    return super().default(obj)
            
            # Create output directory
            os.makedirs(output_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            self.logger.info("🚀 Starting comprehensive REAL market data export...")
            
            export_summary = {
                'export_timestamp': timestamp,
                'data_source': 'kite_api_real_data',
                'exported_files': [],
                'stats': {}
            }
            
            # 1. Export all symbols data
            self.logger.info("📊 Exporting all real symbols...")
            symbols_data = self.get_all_symbols()
            symbols_file = os.path.join(output_dir, f"all_symbols_{timestamp}.json")
            with open(symbols_file, 'w') as f:
                json.dump(symbols_data, f, indent=2, cls=DateTimeEncoder)
            export_summary['exported_files'].append(symbols_file)
            export_summary['stats']['total_symbols'] = symbols_data.get('total_symbols', 0)
            
            # 2. Export all expiries for all symbols
            self.logger.info("📅 Exporting all expiries for all symbols...")
            all_expiries = self.get_all_expiries_for_all_symbols()
            expiries_file = os.path.join(output_dir, f"all_expiries_{timestamp}.json")
            with open(expiries_file, 'w') as f:
                json.dump(all_expiries, f, indent=2, cls=DateTimeEncoder)
            export_summary['exported_files'].append(expiries_file)
            export_summary['stats']['symbols_with_options'] = len(all_expiries)
            
            # 3. Export spot prices for all indices
            self.logger.info("💰 Exporting spot prices for all indices...")
            indices_spot_data = {}
            for symbol in symbols_data.get('indices', []):
                try:
                    spot_data = self.get_spot_price(symbol)
                    indices_spot_data[symbol] = spot_data
                except Exception as e:
                    self.logger.error(f"Error getting spot price for {symbol}: {e}")
            
            if indices_spot_data:
                indices_file = os.path.join(output_dir, f"indices_spot_prices_{timestamp}.json")
                with open(indices_file, 'w') as f:
                    json.dump(indices_spot_data, f, indent=2, cls=DateTimeEncoder)
                export_summary['exported_files'].append(indices_file)
                export_summary['stats']['indices_exported'] = len(indices_spot_data)
            
            # 4. Export option chains for all indices (first 3 expiries each)
            self.logger.info("⚡ Exporting option chains for all indices...")
            option_chains_exported = 0
            
            for symbol in symbols_data.get('indices', []):
                if symbol in all_expiries:
                    symbol_expiries = all_expiries[symbol][:3]  # First 3 expiries
                    
                    for expiry in symbol_expiries:
                        try:
                            self.logger.info(f"Fetching option chain for {symbol} {expiry}...")
                            option_chain = self.get_option_chain(symbol, expiry, include_all_strikes=True)
                            
                            if option_chain and option_chain.get('option_chain'):
                                chain_file = os.path.join(output_dir, f"{symbol}_option_chain_{expiry}_{timestamp}.json")
                                with open(chain_file, 'w') as f:
                                    json.dump(option_chain, f, indent=2, cls=DateTimeEncoder)
                                export_summary['exported_files'].append(chain_file)
                                option_chains_exported += 1
                                
                                self.logger.info(f"✅ Exported {len(option_chain['option_chain'])} options for {symbol} {expiry}")
                            
                            # Rate limiting
                            import time
                            time.sleep(1)
                            
                        except Exception as e:
                            self.logger.error(f"Error exporting option chain for {symbol} {expiry}: {e}")
            
            export_summary['stats']['option_chains_exported'] = option_chains_exported
            
            # 5. Export sample stock data (top 50 stocks)
            self.logger.info("📈 Exporting sample stock spot prices...")
            sample_stocks = symbols_data.get('stocks_with_options', [])[:50]  # Top 50 stocks with options
            stocks_spot_data = {}
            
            for symbol in sample_stocks:
                try:
                    spot_data = self.get_spot_price(symbol)
                    if spot_data['spot_price'] > 0:
                        stocks_spot_data[symbol] = spot_data
                except Exception as e:
                    self.logger.error(f"Error getting spot price for stock {symbol}: {e}")
            
            if stocks_spot_data:
                stocks_file = os.path.join(output_dir, f"sample_stocks_spot_prices_{timestamp}.json")
                with open(stocks_file, 'w') as f:
                    json.dump(stocks_spot_data, f, indent=2, cls=DateTimeEncoder)
                export_summary['exported_files'].append(stocks_file)
                export_summary['stats']['stocks_exported'] = len(stocks_spot_data)
            
            # 6. Export market instruments summary
            self.logger.info("🔧 Exporting instruments summary...")
            instruments_summary = {}
            
            for exchange in ['NSE', 'BSE', 'NFO', 'BFO']:
                try:
                    instruments = self._get_instruments(exchange)
                    if not instruments.empty:
                        instruments_summary[exchange] = {
                            'total_instruments': len(instruments),
                            'instrument_types': instruments['instrument_type'].value_counts().to_dict(),
                            'sample_instruments': instruments.head(10).to_dict('records')
                        }
                except Exception as e:
                    self.logger.error(f"Error getting instruments summary for {exchange}: {e}")
            
            if instruments_summary:
                instruments_file = os.path.join(output_dir, f"instruments_summary_{timestamp}.json")
                with open(instruments_file, 'w') as f:
                    json.dump(instruments_summary, f, indent=2, cls=DateTimeEncoder)
                export_summary['exported_files'].append(instruments_file)
            
            # 7. Save export summary
            summary_file = os.path.join(output_dir, f"export_summary_{timestamp}.json")
            with open(summary_file, 'w') as f:
                json.dump(export_summary, f, indent=2, cls=DateTimeEncoder)
            
            self.logger.info(f"🎉 Comprehensive data export completed!")
            self.logger.info(f"📁 Exported {len(export_summary['exported_files'])} files to {output_dir}")
            self.logger.info(f"📊 Stats: {export_summary['stats']}")
            
            return {
                'success': True,
                'output_directory': output_dir,
                'files_exported': len(export_summary['exported_files']),
                'summary': export_summary,
                'message': 'All real market data exported successfully!'
            }
            
        except Exception as e:
            self.logger.error(f"❌ Error during comprehensive data export: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': 'Data export failed'
            }

    def test_connection(self) -> Dict[str, Any]:
        """Test Kite API connection"""
        try:
            try:
                profile = self.kite.profile()
            except Exception:
                # Attempt refresh via token service and retry once
                try:
                    kite_token_service.ensure_valid(self.kite)
                    profile = self.kite.profile()
                except Exception as e:
                    raise e
            return {
                'success': True,
                'user_name': profile.get('user_name', 'Unknown'),
                'user_id': profile.get('user_id', 'Unknown'),
                'email': profile.get('email', 'Unknown'),
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            self.logger.error(f"❌ Connection test failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }

# Create singleton instance
kite_api_service = KiteAPIService()
