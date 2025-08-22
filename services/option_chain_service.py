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
        self.cache_timeout = 1  # 1 second for real-time updates
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
    
    def _get_market_phase_data(self, symbol: str) -> Dict:
        """Get market phase data for a symbol"""
        try:
            # For now, return mock market phase data
            # In future, this could fetch real market hours from Kite API
            return {
                'market_phase': 'MARKET_HOURS',
                'is_market_open': True,
                'next_market_close': '15:30:00',
                'market_status': 'OPEN'
            }
        except Exception as e:
            logger.error(f"Error getting market phase data for {symbol}: {e}")
            return {
                'market_phase': 'UNKNOWN',
                'is_market_open': False,
                'next_market_close': None,
                'market_status': 'UNKNOWN'
            }

    def get_advanced_option_analysis(self, symbol: str, expiry: Optional[str] = None) -> Dict:
        """Compute a minimal advanced analysis from the option chain.

        Returns a dict with keys used by routes: option_data (itm/atm/otm lists),
        aggregate_statistics (market_sentiment), pcr_oi, pcr_volume, support_resistance, ohlc_data.
        """
        try:
            chain = self.kite_service.get_option_chain(symbol, expiry)
            rows = chain.get('option_chain', []) if isinstance(chain, dict) else []
            atm = chain.get('atm_strike')
            pcr_oi = float(chain.get('pcr_oi', 0) or 0)
            total_ce_volume = float(chain.get('total_ce_volume', 0) or 0)
            total_pe_volume = float(chain.get('total_pe_volume', 0) or 0)
            pcr_volume = (total_pe_volume / total_ce_volume) if total_ce_volume > 0 else 0

            # Split ITM/ATM/OTM by strike vs ATM
            itm_strikes = [r for r in rows if r.get('strike_price') and atm and r['strike_price'] != atm and (
                (r['strike_price'] < atm) or (r['strike_price'] > atm)
            )]
            atm_strikes = [r for r in rows if r.get('strike_price') == atm]
            # For simplicity, treat OTM as same set as ITM complement; UI can filter further if needed
            otm_strikes = [r for r in rows if r.get('strike_price') and r not in atm_strikes]

            # Sentiment by PCR OI
            if pcr_oi < 0.9:
                sentiment = 'BULLISH'
            elif pcr_oi > 1.1:
                sentiment = 'BEARISH'
            else:
                sentiment = 'NEUTRAL'

            # Basic SR from CE/PE highs around ATM (fallbacks)
            highs = [max(r.get('ce_high') or 0, r.get('pe_high') or 0) for r in atm_strikes] or [0]
            lows = [min(v for v in [r.get('ce_low'), r.get('pe_low')] if v is not None) for r in atm_strikes] or [0]
            support_resistance = {
                'support': min(lows) if lows else 0,
                'resistance': max(highs) if highs else 0
            }

            # Minimal OHLC panel: use market service when available; here return placeholders
            ohlc_data = {
                'spot_price': chain.get('spot_price'),
                'previous_close': chain.get('previous_close')
            }

            return {
                'option_data': {
                    'itm_strikes': itm_strikes,
                    'atm_strikes': atm_strikes,
                    'otm_strikes': otm_strikes
                },
                'aggregate_statistics': {
                    'market_sentiment': sentiment
                },
                'pcr_oi': pcr_oi,
                'pcr_volume': pcr_volume,
                'support_resistance': support_resistance,
                'ohlc_data': ohlc_data,
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error in advanced option analysis for {symbol}: {e}")
            return {
                'option_data': { 'itm_strikes': [], 'atm_strikes': [], 'otm_strikes': [] },
                'aggregate_statistics': { 'market_sentiment': 'UNKNOWN' },
                'pcr_oi': 0,
                'pcr_volume': 0,
                'support_resistance': { 'support': 0, 'resistance': 0 },
                'ohlc_data': {},
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            }

    def calculate_sharpe_score(self, analysis_data: Dict) -> float:
        """Replicate simple SHARPE score logic used by routes."""
        try:
            pcr_oi = float(analysis_data.get('pcr_oi', 0) or 0)
            pcr_volume = float(analysis_data.get('pcr_volume', 0) or 0)
            pcr_score = 1 - abs(1.0 - (pcr_oi + pcr_volume) / 2)
            sentiment = (analysis_data.get('aggregate_statistics') or {}).get('market_sentiment', 'NEUTRAL')
            sentiment_multiplier = {'BULLISH': 1.2, 'NEUTRAL': 1.0, 'BEARISH': 0.8}.get(sentiment, 1.0)
            return round(pcr_score * sentiment_multiplier * 100, 2)
        except Exception:
            return 50.0

    def generate_sharpe_recommendations(self, analysis_data: Dict) -> List[str]:
        """Basic recommendation strings based on sentiment and PCR."""
        try:
            recs: List[str] = []
            sentiment = (analysis_data.get('aggregate_statistics') or {}).get('market_sentiment', 'NEUTRAL')
            pcr_oi = float(analysis_data.get('pcr_oi', 0) or 0)
            if sentiment == 'BULLISH' and pcr_oi < 0.8:
                recs += ["Consider CALL buying on pullbacks", "Look for PUT selling opportunities"]
            elif sentiment == 'BEARISH' and pcr_oi > 1.2:
                recs += ["Consider PUT buying on rallies", "Look for CALL selling opportunities"]
            else:
                recs += ["Market is neutral - consider range-bound strategies", "Monitor for breakout signals"]
            return recs
        except Exception:
            return ["Monitor market conditions closely"]

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
