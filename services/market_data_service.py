"""
Market Data Service
Handles real-time market data operations using Kite API
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from services.kite_api_service import kite_api_service

logger = logging.getLogger(__name__)

class MarketDataService:
    """Service for handling real-time market data using Kite API"""
    
    def __init__(self):
        self.kite_service = kite_api_service
        self.cache = {}
        self.cache_timeout = 1  # 1 second for real-time updates
        logger.info("MarketDataService initialized with Kite API")
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cache is valid"""
        if cache_key not in self.cache:
            return False
        
        cache_time = self.cache[cache_key].get('timestamp')
        if not cache_time:
            return False
        
        return (datetime.now() - cache_time).seconds < self.cache_timeout
    
    async def get_spot_price(self, symbol: str) -> Dict:
        """Get current spot price for a symbol"""
        try:
            cache_key = f"spot_{symbol}"
            
            # Check cache
            if self._is_cache_valid(cache_key):
                return self.cache[cache_key]['data']
            
            # Fetch from Kite API
            spot_data = self.kite_service.get_spot_price(symbol)
            
            # Format response
            result = {
                'symbol': symbol,
                'ltp': spot_data['spot_price'],
                'change': spot_data['change'],
                'change_percent': spot_data['change_percent'],
                'timestamp': spot_data['timestamp'],
                'volume': spot_data['volume'],
                'previous_close': spot_data['previous_close']
            }
            
            # Cache the result
            self.cache[cache_key] = {
                'data': result,
                'timestamp': datetime.now()
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting spot price for {symbol}: {e}")
            return {
                'symbol': symbol,
                'ltp': 0,
                'change': 0,
                'change_percent': 0,
                'timestamp': datetime.now().isoformat(),
                'volume': 0,
                'previous_close': 0,
                'error': str(e)
            }
    
    def get_spot_price_sync(self, symbol: str) -> Dict:
        """Synchronous version of get_spot_price"""
        try:
            cache_key = f"spot_{symbol}"
            
            # Check cache
            if self._is_cache_valid(cache_key):
                return self.cache[cache_key]['data']
            
            # Fetch from Kite API
            spot_data = self.kite_service.get_spot_price(symbol)
            
            # Format response
            result = {
                'symbol': symbol,
                'ltp': spot_data['spot_price'],
                'change': spot_data['change'],
                'change_percent': spot_data['change_percent'],
                'timestamp': spot_data['timestamp'],
                'volume': spot_data['volume'],
                'previous_close': spot_data['previous_close']
            }
            
            # Cache the result
            self.cache[cache_key] = {
                'data': result,
                'timestamp': datetime.now()
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting spot price for {symbol}: {e}")
            return {
                'symbol': symbol,
                'ltp': 0,
                'change': 0,
                'change_percent': 0,
                'timestamp': datetime.now().isoformat(),
                'volume': 0,
                'previous_close': 0,
                'error': str(e)
            }
    
    def get_market_status(self) -> Dict:
        """Get current market status"""
        try:
            # Get market status from Kite API (if available)
            # For now, return a simple status based on time
            now = datetime.now()
            
            # Market hours: 9:15 AM to 3:30 PM (Indian time)
            market_start = now.replace(hour=9, minute=15, second=0, microsecond=0)
            market_end = now.replace(hour=15, minute=30, second=0, microsecond=0)
            
            is_open = market_start <= now <= market_end and now.weekday() < 5
            
            return {
                'market_open': is_open,
                'market_status': 'open' if is_open else 'closed',
                'timestamp': datetime.now().isoformat(),
                'next_open': market_start.isoformat() if not is_open else None,
                'next_close': market_end.isoformat() if is_open else None
            }
            
        except Exception as e:
            logger.error(f"Error getting market status: {e}")
            return {
                'market_open': False,
                'market_status': 'unknown',
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            }
    
    def get_multiple_quotes(self, symbols: List[str]) -> Dict[str, Dict]:
        """Get quotes for multiple symbols"""
        try:
            results = {}
            for symbol in symbols:
                results[symbol] = self.get_spot_price_sync(symbol)
            return results
            
        except Exception as e:
            logger.error(f"Error getting multiple quotes: {e}")
            return {}
    
    def get_ohlc_data(self, symbol: str) -> Dict:
        """Get OHLC data for a symbol using real daily candles (no estimates).

        Returns the latest daily candle adjusted with live LTP for close/high/low
        where applicable. Falls back safely if history is unavailable.
        """
        try:
            # Live quote
            spot = self.get_spot_price_sync(symbol)

            # Fetch up to last 2 daily candles from Kite (uses internal caching)
            history = self.kite_service.get_recent_daily_history(symbol, 2)

            if history:
                today = history[-1]
                # Adjust with live LTP
                ltp = spot.get('ltp', 0)
                open_v = today.get('open', spot.get('previous_close', 0))
                high_v = max(today.get('high', 0) or 0, ltp or 0)
                # If today's low missing/0, use ltp; else min with ltp
                base_low = today.get('low', 0) or (ltp or 0)
                low_v = min(base_low, ltp or base_low) if base_low else (ltp or 0)
                close_v = ltp or today.get('close', 0) or 0
                volume_v = today.get('volume', 0)
                return {
                    'symbol': symbol,
                    'open': open_v,
                    'high': high_v,
                    'low': low_v,
                    'close': close_v,
                    'volume': volume_v,
                    'timestamp': spot.get('timestamp') or datetime.now().isoformat()
                }

            # Fallback: return based on spot only (no estimates for H/L)
            return {
                'symbol': symbol,
                'open': spot.get('previous_close', 0),
                'high': spot.get('ltp', 0),
                'low': spot.get('ltp', 0),
                'close': spot.get('ltp', 0),
                'volume': spot.get('volume', 0),
                'timestamp': spot.get('timestamp') or datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error getting OHLC data for {symbol}: {e}")
            return {
                'symbol': symbol,
                'open': 0,
                'high': 0,
                'low': 0,
                'close': 0,
                'volume': 0,
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            }

    async def get_historical_data(self, symbol: str, timeframe: str, days: int) -> List[Dict]:
        """Return recent historical data via Kite API (day timeframe only currently).

        If timeframe != '1day' or 'day', we fall back to empty list (not needed for
        Earth Logic). Returns list of dicts ascending by date.
        """
        try:
            if timeframe not in ('1day', 'day', 'DAY', 'Day'):
                return []
            days = max(1, min(days, 5))
            history = self.kite_service.get_recent_daily_history(symbol, days)
            return history
        except Exception as e:
            logger.error(f"Error fetching historical data for {symbol}: {e}")
            return []
    
    def clear_cache(self):
        """Clear all cached data"""
        self.cache.clear()
        logger.info("Market data cache cleared")
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        return {
            'total_entries': len(self.cache),
            'entries': list(self.cache.keys()),
            'cache_timeout': self.cache_timeout
        }
