"""
Option Chain Service
Uses Kite API for real option chain data
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from services.kite_api_service import kite_api_service

logger = logging.getLogger(__name__)

class OptionChainService:
    """Service for handling option chain operations using Kite API"""
    
    def __init__(self):
        self.kite_service = kite_api_service
        self.cache = {}
        self.cache_timeout = 30  # 30 seconds
        logger.info("OptionChainService initialized with Kite API")
    
    def _get_cache_key(self, symbol: str, expiry: str = None) -> str:
        """Generate cache key"""
        return f"{symbol}_{expiry or 'latest'}"
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cache is valid"""
        if cache_key not in self.cache:
            return False
        
        cache_time = self.cache[cache_key].get('timestamp')
        if not cache_time:
            return False
        
        return (datetime.now() - cache_time).seconds < self.cache_timeout
    
    def get_symbols(self) -> Dict[str, List[str]]:
        """Get all available symbols"""
        try:
            return self.kite_service.get_all_symbols()
        except Exception as e:
            logger.error(f"Error getting symbols: {e}")
            return {'indices': [], 'stocks': [], 'all': []}
    
    def get_expiries(self, symbol: str) -> List[str]:
        """Get expiry dates for a symbol"""
        try:
            cache_key = f"expiries_{symbol}"
            
            # Check cache (longer cache for expiries - 1 hour)
            if (cache_key in self.cache and 
                (datetime.now() - self.cache[cache_key]['timestamp']).seconds < 3600):
                return self.cache[cache_key]['data']
            
            expiries = self.kite_service.get_expiry_dates(symbol)
            
            # Cache the result
            self.cache[cache_key] = {
                'data': expiries,
                'timestamp': datetime.now()
            }
            
            return expiries
            
        except Exception as e:
            logger.error(f"Error getting expiries for {symbol}: {e}")
            return []
    
    def get_spot_price(self, symbol: str) -> Dict:
        """Get spot price for a symbol"""
        try:
            return self.kite_service.get_spot_price(symbol)
        except Exception as e:
            logger.error(f"Error getting spot price for {symbol}: {e}")
            return {
                'symbol': symbol,
                'spot_price': 0,
                'previous_close': 0,
                'change': 0,
                'change_percent': 0,
                'volume': 0,
                'timestamp': datetime.now().isoformat()
            }
    
    def get_option_chain(self, symbol: str, expiry: str = None) -> Dict:
        """Get option chain data"""
        try:
            cache_key = self._get_cache_key(symbol, expiry)
            
            # Check cache
            if self._is_cache_valid(cache_key):
                logger.info(f"Returning cached option chain for {cache_key}")
                return self.cache[cache_key]['data']
            
            # Fetch from Kite API
            option_chain_data = self.kite_service.get_option_chain(symbol, expiry)
            
            # Cache the data
            self.cache[cache_key] = {
                'data': option_chain_data,
                'timestamp': datetime.now()
            }
            
            logger.info(f"✅ Successfully fetched option chain for {symbol} {expiry}")
            return option_chain_data
            
        except Exception as e:
            logger.error(f"❌ Error getting option chain for {symbol}: {e}")
            # Return error response instead of raising
            return {
                'symbol': symbol,
                'expiry': expiry,
                'error': str(e),
                'spot_price': 0,
                'option_chain': [],
                'timestamp': datetime.now().isoformat(),
                'data_source': 'error'
            }
    
    def get_dashboard_data(self, symbol: str, expiry: str = None) -> Dict:
        """Get dashboard data for a symbol"""
        try:
            cache_key = f"dashboard_{self._get_cache_key(symbol, expiry)}"
            
            # Check cache
            if self._is_cache_valid(cache_key):
                logger.info(f"Returning cached dashboard data for {cache_key}")
                return self.cache[cache_key]['data']
            
            # Fetch from Kite API
            dashboard_data = self.kite_service.get_dashboard_data(symbol, expiry)
            
            # Cache the data
            self.cache[cache_key] = {
                'data': dashboard_data,
                'timestamp': datetime.now()
            }
            
            logger.info(f"✅ Successfully fetched dashboard data for {symbol}")
            return dashboard_data
            
        except Exception as e:
            logger.error(f"❌ Error getting dashboard data for {symbol}: {e}")
            # Return error response instead of raising
            return {
                'symbol': symbol,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def test_connection(self) -> Dict:
        """Test Kite API connection"""
        try:
            return self.kite_service.test_connection()
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def clear_cache(self):
        """Clear all cached data"""
        self.cache.clear()
        logger.info("Cache cleared")
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        return {
            'total_entries': len(self.cache),
            'entries': list(self.cache.keys()),
            'cache_timeout': self.cache_timeout
        }
