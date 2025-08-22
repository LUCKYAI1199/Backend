"""
API Routes for Trading Platform Backend
Handles all REST API endpoints with proper service integration
"""

from flask import Blueprint, request, jsonify, current_app
import os
from datetime import datetime, time as dtime, timedelta
import logging
import time

# Import utilities
from utils.response_formatter import ResponseFormatter
from utils.validators import Validators, ValidationError
from utils.error_handlers import APIException

# Simple rate limiting cache
rate_limit_cache = {}
RATE_LIMIT_WINDOW = 2  # 2 seconds cooldown between same requests

def check_rate_limit(key: str) -> bool:
    """Check if request is within rate limit"""
    now = time.time()
    if key in rate_limit_cache:
        if now - rate_limit_cache[key] < RATE_LIMIT_WINDOW:
            return False
    rate_limit_cache[key] = now
    return True

logger = logging.getLogger(__name__)

# Create blueprint
api_blueprint = Blueprint('api', __name__)

# Shared-secret checker for scheduler/refresh endpoints
def _check_refresh_secret() -> bool:
    secret = os.environ.get('KITE_REFRESH_SECRET')
    if not secret:
        return True  # no secret configured
    provided = request.headers.get('X-Refresh-Secret') or request.args.get('secret')
    return provided == secret

# Health check endpoint
@api_blueprint.route('/health', methods=['GET'])
def health_check():
    """API health check"""
    try:
        services_status = {
            "option_chain": {"healthy": True, "status": "operational"},
            "market_data": {"healthy": True, "status": "operational"},
            "api": {"healthy": True, "status": "operational"}
        }
        
        return jsonify(ResponseFormatter.health_check_response(services_status))
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return jsonify(ResponseFormatter.error("Health check failed")), 500

# Lightweight API status endpoint (frontend expects /api/status)
@api_blueprint.route('/status', methods=['GET'])
def api_status():
    try:
        return jsonify({
            "status": "ok",
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Status endpoint error: {e}")
        return jsonify(ResponseFormatter.error("Status check failed")), 500

@api_blueprint.route('/scheduler/kite-daily-refresh', methods=['POST'])
def scheduler_kite_daily_refresh():
    """Endpoint for Render Scheduler to call daily to refresh tokens.

    Optional JSON: { "utc": true } if the scheduler time is already in UTC.
    We don't compute timing here; caller schedules appropriately (e.g., 23:00 UTC).
    """
    try:
        if not _check_refresh_secret():
            return jsonify(ResponseFormatter.error('Unauthorized')), 401
        from services.kite_token_service import kite_token_service
        saved = kite_token_service.refresh_tokens()
        return jsonify(ResponseFormatter.success(data={'saved': saved}, message='Daily token refresh completed'))
    except Exception as e:
        logger.error(f"Scheduler refresh error: {e}")
        return jsonify(ResponseFormatter.error('Daily token refresh failed')), 500

# Market status alias to match frontend (underscored path)
@api_blueprint.route('/market_status', methods=['GET'])
def market_status_alias():
    try:
        market_service = current_app.market_service
        raw = market_service.get_market_status()
        # Map to frontend expected fields
        is_open = bool(raw.get('market_open'))
        phase = raw.get('market_status', 'unknown')
        next_change = raw.get('next_close') if is_open else raw.get('next_open')
        return jsonify({
            "isOpen": is_open,
            "phase": phase,
            "nextChange": next_change or ""
        })
    except Exception as e:
        logger.error(f"Market status error: {e}")
        return jsonify(ResponseFormatter.error("Failed to fetch market status")), 500

# Additional Sharp Pro signals - today
@api_blueprint.route('/sharp-pro/signals/today', methods=['GET'])
def get_sharp_pro_signals_today():
    try:
        from services.additional_sharp_pro_signal_service import get_today_hits
        hits = get_today_hits()
        return jsonify(ResponseFormatter.success(data={'signals': hits}, message='Today\'s ASP signals'))
    except Exception as e:
        logger.error(f"Error fetching ASP signals today: {e}")
        return jsonify(ResponseFormatter.error("Failed to fetch ASP signals")), 500

# Real Data API endpoints (comprehensive Kite API integration)
@api_blueprint.route('/real-data/all-symbols', methods=['GET'])
def get_all_real_symbols():
    """Get ALL real symbols from Kite API - indices, stocks, and stocks with options"""
    try:
        # Get Kite API service
        from services.kite_api_service import kite_api_service
        
        # Fetch ALL real symbols
        symbols_data = kite_api_service.get_all_symbols()
        
        return jsonify(ResponseFormatter.success(
            data=symbols_data,
            message="All real symbols retrieved successfully from Kite API",
            meta={
                "data_source": "kite_api",
                "total_indices": symbols_data.get('total_indices', 0),
                "total_stocks": symbols_data.get('total_stocks', 0),
                "total_stocks_with_options": symbols_data.get('total_stocks_with_options', 0)
            }
        ))
        
    except Exception as e:
        logger.error(f"Error fetching all real symbols: {e}")
        return jsonify(ResponseFormatter.error("Failed to fetch real symbols data")), 500

@api_blueprint.route('/real-data/all-expiries', methods=['GET'])
def get_all_real_expiries():
    """Get ALL expiry dates for ALL symbols that have options"""
    try:
        # Get Kite API service
        from services.kite_api_service import kite_api_service
        
        # Fetch ALL expiries for ALL symbols
        all_expiries = kite_api_service.get_all_expiries_for_all_symbols()
        
        return jsonify(ResponseFormatter.success(
            data=all_expiries,
            message="All expiry dates for all symbols retrieved successfully",
            meta={
                "data_source": "kite_api",
                "symbols_with_options": len(all_expiries),
                "total_expiries": sum(len(expiries) for expiries in all_expiries.values())
            }
        ))
        
    except Exception as e:
        logger.error(f"Error fetching all expiries: {e}")
        return jsonify(ResponseFormatter.error("Failed to fetch all expiries data")), 500

@api_blueprint.route('/real-data/option-chain/<symbol>', methods=['GET'])
def get_real_option_chain(symbol):
    """Get COMPLETE real option chain with ALL strikes for a symbol"""
    try:
        # Validate symbol
        symbol = Validators.validate_symbol(symbol)
        
        # Get parameters
        expiry = request.args.get('expiry')
        include_all_strikes = request.args.get('include_all_strikes', 'true').lower() == 'true'
        
        if expiry:
            expiry = Validators.validate_expiry_date(expiry)
        
        # Get Kite API service
        from services.kite_api_service import kite_api_service
        
        # Fetch COMPLETE option chain with ALL strikes
        option_data = kite_api_service.get_option_chain(
            symbol=symbol, 
            expiry=expiry, 
            include_all_strikes=include_all_strikes
        )
        
        return jsonify(ResponseFormatter.success(
            data=option_data,
            message=f"Complete real option chain for {symbol} retrieved successfully",
            meta={
                "symbol": symbol,
                "expiry": expiry,
                "data_source": "kite_api",
                "total_strikes": len(option_data.get('option_chain', [])),
                "all_strikes_included": include_all_strikes
            }
        ))
        
    except ValidationError as e:
        return jsonify(ResponseFormatter.validation_error(e.field, e.message, e.value)), 400
    except Exception as e:
        logger.error(f"Error fetching real option chain for {symbol}: {e}")
        # Include exception in message for direct visibility in clients
        return jsonify(ResponseFormatter.error(
            message=f"Failed to fetch real option chain for {symbol}: {str(e)}",
            details={
                "symbol": symbol,
                "expiry": expiry,
                "exception": str(e)
            }
        )), 500

@api_blueprint.route('/real-data/expiries/<symbol>', methods=['GET'])
def get_real_expiries(symbol):
    """Get real expiry dates for a specific symbol from Kite API"""
    try:
        # Rate limiting
        rate_key = f"expiries_{symbol}_{request.remote_addr}"
        if not check_rate_limit(rate_key):
            return jsonify(ResponseFormatter.error("Rate limit exceeded. Please wait before retrying.")), 429
        
        # Validate symbol
        symbol = Validators.validate_symbol(symbol)
        
        # Get Kite API service
        from services.kite_api_service import kite_api_service
        
        # Fetch real expiries for the symbol
        expiries = kite_api_service.get_expiry_dates(symbol)
        
        return jsonify(ResponseFormatter.success(
            data={"expiry_dates": expiries},
            message=f"Real expiry dates for {symbol} retrieved successfully",
            meta={
                "symbol": symbol,
                "count": len(expiries),
                "data_source": "kite_api"
            }
        ))
        
    except ValidationError as e:
        return jsonify(ResponseFormatter.validation_error(e.field, e.message, e.value)), 400
    except Exception as e:
        logger.error(f"Error fetching real expiries for {symbol}: {e}")
        return jsonify(ResponseFormatter.error(f"Failed to fetch real expiries for {symbol}")), 500

@api_blueprint.route('/real-data/export', methods=['POST'])
def export_all_real_data():
    """Export ALL real market data to files - comprehensive data dump"""
    try:
        # Get parameters
        output_dir = request.json.get('output_dir', 'real_market_data_export') if request.json else 'real_market_data_export'
        
        # Get Kite API service
        from services.kite_api_service import kite_api_service
        
        # Export ALL real data
        export_result = kite_api_service.export_all_market_data(output_dir)
        
        if export_result['success']:
            return jsonify(ResponseFormatter.success(
                data=export_result,
                message="All real market data exported successfully!",
                meta={
                    "data_source": "kite_api",
                    "files_exported": export_result.get('files_exported', 0),
                    "output_directory": export_result.get('output_directory')
                }
            ))
        else:
            return jsonify(ResponseFormatter.error(export_result.get('message', 'Export failed'))), 500
        
    except Exception as e:
        logger.error(f"Error exporting all real data: {e}")
        return jsonify(ResponseFormatter.error("Failed to export real market data")), 500

@api_blueprint.route('/real-data/test-connection', methods=['GET'])
def test_kite_connection():
    """Test Kite API connection and show user details"""
    try:
        # Get Kite API service
        from services.kite_api_service import kite_api_service
        
        # Test connection
        connection_result = kite_api_service.test_connection()
        
        if connection_result['success']:
            return jsonify(ResponseFormatter.success(
                data=connection_result,
                message="Kite API connection successful!",
                meta={"data_source": "kite_api"}
            ))
        else:
            return jsonify(ResponseFormatter.error(
                f"Kite API connection failed: {connection_result.get('error', 'Unknown error')}"
            )), 500
        
    except Exception as e:
        logger.error(f"Error testing Kite connection: {e}")
        return jsonify(ResponseFormatter.error("Failed to test Kite API connection")), 500

# ---------------- Kite token management ---------------- #
@api_blueprint.route('/kite/token/bootstrap', methods=['POST'])
def kite_token_bootstrap():
    """Exchange a one-time request_token and persist tokens in DB."""
    try:
        if not _check_refresh_secret():
            return jsonify(ResponseFormatter.error('Unauthorized')), 401
        payload = request.get_json(silent=True) or {}
        request_token = payload.get('request_token')
        if not request_token:
            return jsonify(ResponseFormatter.validation_error('request_token', 'request_token is required', None)), 400
        from services.kite_token_service import kite_token_service
        saved = kite_token_service.bootstrap_with_request_token(request_token)
        return jsonify(ResponseFormatter.success(data={'saved': saved}, message='Kite tokens bootstrapped'))
    except Exception as e:
        logger.error(f"Kite token bootstrap error: {e}")
        return jsonify(ResponseFormatter.error('Failed to bootstrap tokens')), 500

@api_blueprint.route('/kite/token/refresh', methods=['POST'])
def kite_token_refresh():
    """Refresh access token using stored refresh token; rotate and persist."""
    try:
        if not _check_refresh_secret():
            return jsonify(ResponseFormatter.error('Unauthorized')), 401
        from services.kite_token_service import kite_token_service
        saved = kite_token_service.refresh_tokens()
        return jsonify(ResponseFormatter.success(data={'saved': saved}, message='Kite tokens refreshed'))
    except Exception as e:
        logger.error(f"Kite token refresh error: {e}")
        return jsonify(ResponseFormatter.error('Failed to refresh tokens')), 500

@api_blueprint.route('/websocket/test', methods=['POST'])
def test_websocket_connection():
    """Test WebSocket connection by emitting a test signal"""
    try:
        # Get WebSocket service from current app
        websocket_service = current_app.websocket_service
        
        # Emit test signal
        websocket_service.emit_test_signal()
        
        # Get connection stats
        stats = websocket_service.get_subscription_stats()
        
        return jsonify(ResponseFormatter.success(
            data={
                "test_signal_sent": True,
                "connection_stats": stats
            },
            message="Test signal emitted successfully"
        ))
        
    except Exception as e:
        logger.error(f"Error testing WebSocket connection: {e}")
        return jsonify(ResponseFormatter.error("Failed to test WebSocket connection")), 500

# Symbol-related endpoints
@api_blueprint.route('/symbols', methods=['GET'])
def get_symbols():
    """Get available symbols"""
    try:
        # Get service instance
        option_service = current_app.option_service
        
        # Fetch symbols from Kite API service
        symbols = option_service.get_symbols()
        
        return jsonify(ResponseFormatter.success(
            data=symbols,
            message="Available symbols retrieved successfully"
        ))
        
    except Exception as e:
        logger.error(f"Error fetching symbols: {e}")
        return jsonify(ResponseFormatter.error("Failed to fetch symbols")), 500

@api_blueprint.route('/symbols/<symbol>/expiries', methods=['GET'])
def get_symbol_expiries(symbol):
    """Get expiry dates for a symbol"""
    try:
        # Validate symbol
        symbol = Validators.validate_symbol(symbol)
        
        # Get service instance
        option_service = current_app.option_service
        
        # Fetch expiries
        expiries = option_service.get_expiries(symbol)
        
        return jsonify(ResponseFormatter.success(
            data=expiries,
            message=f"Expiry dates for {symbol} retrieved successfully",
            meta={"symbol": symbol, "count": len(expiries)}
        ))
        
    except ValidationError as e:
        return jsonify(ResponseFormatter.validation_error(e.field, e.message, e.value)), 400
    except Exception as e:
        logger.error(f"Error fetching expiries for {symbol}: {e}")
        return jsonify(ResponseFormatter.error(f"Failed to fetch expiries for {symbol}")), 500

@api_blueprint.route('/symbols/<symbol>/spot-price', methods=['GET'])
def get_symbol_spot_price(symbol):
    """Get current spot price for a symbol"""
    try:
        # Validate symbol
        symbol = Validators.validate_symbol(symbol)
        
        # Get service instance
        market_service = current_app.market_service
        
        # Fetch spot price using synchronous method
        spot_data = market_service.get_spot_price_sync(symbol)
        
        return jsonify(ResponseFormatter.market_data_response(spot_data, symbol))
        
    except ValidationError as e:
        return jsonify(ResponseFormatter.validation_error(e.field, e.message, e.value)), 400
    except Exception as e:
        logger.error(f"Error fetching spot price for {symbol}: {e}")
        return jsonify(ResponseFormatter.error(f"Failed to fetch spot price for {symbol}")), 500

# Option chain endpoints
@api_blueprint.route('/option-chain', methods=['GET'])
def get_option_chain():
    """Get option chain data"""
    try:
        # Get and validate parameters
        symbol = request.args.get('symbol')
        expiry = request.args.get('expiry')
        
        if not symbol:
            return jsonify(ResponseFormatter.validation_error('symbol', 'Symbol parameter is required')), 400
        
        symbol = Validators.validate_symbol(symbol)
        
        if expiry:
            expiry = Validators.validate_expiry_date(expiry)
        
        # Get service instance
        option_service = current_app.option_service
        
        # Fetch option chain data
        option_data = option_service.get_option_chain(symbol, expiry)
        
        return jsonify(ResponseFormatter.option_chain_response(option_data, symbol, expiry))
        
    except ValidationError as e:
        return jsonify(ResponseFormatter.validation_error(e.field, e.message, e.value)), 400
    except Exception as e:
        logger.error(f"Error fetching option chain: {e}")
        return jsonify(ResponseFormatter.error("Failed to fetch option chain data")), 500

@api_blueprint.route('/dashboard-data', methods=['GET'])
def get_dashboard_data():
    """Get dashboard metrics"""
    try:
        # Get and validate parameters
        symbol = request.args.get('symbol')
        expiry = request.args.get('expiry')
        
        if not symbol:
            return jsonify(ResponseFormatter.validation_error('symbol', 'Symbol parameter is required')), 400
        
        symbol = Validators.validate_symbol(symbol)
        
        if expiry:
            expiry = Validators.validate_expiry_date(expiry)
        
        # Get service instance
        option_service = current_app.option_service
        
        # Fetch dashboard data
        dashboard_data = option_service.get_dashboard_data(symbol, expiry)
        
        return jsonify(ResponseFormatter.success(
            data=dashboard_data,
            message=f"Dashboard data for {symbol} retrieved successfully"
        ))
        
    except ValidationError as e:
        return jsonify(ResponseFormatter.validation_error(e.field, e.message, e.value)), 400
    except Exception as e:
        logger.error(f"Error fetching dashboard data: {e}")
        return jsonify(ResponseFormatter.error("Failed to fetch dashboard data")), 500

# Market data endpoints
@api_blueprint.route('/market-status', methods=['GET'])
def get_market_status():
    """Get current market status"""
    try:
        # Get service instance
        market_service = current_app.market_service
        
        # Get market status
        market_status = market_service.get_market_status()
        
        return jsonify(ResponseFormatter.success(
            data=market_status,
            message="Market status retrieved successfully"
        ))
        
    except Exception as e:
        logger.error(f"Error fetching market status: {e}")
        return jsonify(ResponseFormatter.error("Failed to fetch market status")), 500

@api_blueprint.route('/historical-data/<symbol>', methods=['GET'])
def get_historical_data(symbol):
    """Get historical data for a symbol"""
    try:
        # Validate symbol
        symbol = Validators.validate_symbol(symbol)
        
        # Get and validate parameters
        timeframe = request.args.get('timeframe', '1min')
        days = int(request.args.get('days', 1))
        
        timeframe = Validators.validate_timeframe(timeframe)
        
        # Get service instance
        market_service = current_app.market_service
        
        # Fetch historical data (async call)
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            historical_data = loop.run_until_complete(
                market_service.get_historical_data(symbol, timeframe, days)
            )
        finally:
            loop.close()
        
        return jsonify(ResponseFormatter.success(
            data=historical_data,
            message=f"Historical data for {symbol} retrieved successfully",
            meta={
                "symbol": symbol,
                "timeframe": timeframe,
                "days": days,
                "data_points": len(historical_data)
            }
        ))
        
    except ValidationError as e:
        return jsonify(ResponseFormatter.validation_error(e.field, e.message, e.value)), 400
    except Exception as e:
        logger.error(f"Error fetching historical data for {symbol}: {e}")
        return jsonify(ResponseFormatter.error(f"Failed to fetch historical data for {symbol}")), 500

# Legacy endpoint compatibility (for existing frontend calls)
@api_blueprint.route('/expiries/<symbol>', methods=['GET'])
def get_expiries_legacy(symbol):
    """Legacy endpoint for expiry dates - matches frontend ApiService.getExpiries()"""
    try:
        symbol = Validators.validate_symbol(symbol)
        option_service = current_app.option_service
        expiries = option_service.get_expiries(symbol)
        
        # Return in format expected by frontend: { expiries: string[] }
        return jsonify({
            'expiries': expiries
        })
        
    except ValidationError as e:
        return jsonify({'error': e.message}), 400
    except Exception as e:
        logger.error(f"Error in legacy expiries endpoint: {e}")
        return jsonify({'error': str(e)}), 500

@api_blueprint.route('/spot_price/<symbol>', methods=['GET'])
def get_spot_price_legacy(symbol):
    """Legacy endpoint for spot price - matches frontend ApiService.getSpotPrice()"""
    try:
        symbol = Validators.validate_symbol(symbol)
        market_service = current_app.market_service
        
        # Get spot price
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            spot_data = loop.run_until_complete(market_service.get_spot_price(symbol))
        finally:
            loop.close()
        
        # Return in format expected by frontend: { price, change, change_percent }
        return jsonify({
            'price': spot_data['ltp'],
            'change': spot_data['change'],
            'change_percent': spot_data['change_percent']
        })
        
    except ValidationError as e:
        return jsonify({'error': e.message}), 400
    except Exception as e:
        logger.error(f"Error in legacy spot price endpoint: {e}")
        return jsonify({'error': str(e)}), 500

@api_blueprint.route('/option_chain', methods=['GET'])
def get_option_chain_legacy():
    """Legacy endpoint for option chain - matches frontend ApiService.getOptionChain()"""
    try:
        symbol = request.args.get('symbol')
        expiry = request.args.get('expiry')
        
        if not symbol:
            return jsonify({'error': 'Symbol parameter is required'}), 400
        
        symbol = Validators.validate_symbol(symbol)
        
        if expiry:
            expiry = Validators.validate_expiry_date(expiry)
        
        option_service = current_app.option_service
        option_data = option_service.get_option_chain(symbol, expiry)
        
        # Return in format expected by frontend OptionChainResponse
        return jsonify({
            'symbol': symbol,
            'expiry': expiry,
            'spot_price': option_data.get('spot_price'),
            'option_chain': option_data.get('option_chain', []),
            'atm_strike': option_data.get('atm_strike'),
            'total_ce_oi': option_data.get('total_ce_oi', 0),
            'total_pe_oi': option_data.get('total_pe_oi', 0),
            'total_ce_volume': option_data.get('total_ce_volume', 0),
            'total_pe_volume': option_data.get('total_pe_volume', 0),
            'pcr_oi': option_data.get('pcr_oi', 0),
            'max_pain': option_data.get('max_pain'),
            'timestamp': datetime.now().isoformat()
        })
        
    except ValidationError as e:
        return jsonify({'error': e.message}), 400
    except Exception as e:
        logger.error(f"Error in legacy option chain endpoint: {e}")
        return jsonify({'error': str(e)}), 500

@api_blueprint.route('/dashboard_data', methods=['GET'])
def get_dashboard_data_legacy():
    """Legacy endpoint for dashboard data"""
    try:
        symbol = request.args.get('symbol')
        expiry = request.args.get('expiry')
        
        if not symbol:
            return jsonify({'error': 'Symbol parameter is required'}), 400
        
        symbol = Validators.validate_symbol(symbol)
        
        if expiry:
            expiry = Validators.validate_expiry_date(expiry)
        
        option_service = current_app.option_service
        dashboard_data = option_service.get_dashboard_data(symbol, expiry)
        
        return jsonify(dashboard_data)
        
    except ValidationError as e:
        return jsonify({'error': e.message}), 400
    except Exception as e:
        logger.error(f"Error in legacy dashboard endpoint: {e}")
        return jsonify({'error': str(e)}), 500

# OHLC endpoints for compatibility
@api_blueprint.route('/ohlc_data/<symbol>', methods=['GET'])
def get_ohlc_data(symbol):
    """Get OHLC data for a symbol"""
    try:
        symbol = Validators.validate_symbol(symbol)
        market_service = current_app.market_service
        
        # Get spot price and generate OHLC data
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            spot_data = loop.run_until_complete(market_service.get_spot_price(symbol))
            historical_data = loop.run_until_complete(
                market_service.get_historical_data(symbol, '1day', 2)
            )
        finally:
            loop.close()
        
        # Format OHLC response
        current_day = None
        previous_day = None
        
        if historical_data and len(historical_data) >= 2:
            previous_day = historical_data[-2]
            current_day = historical_data[-1]
            # Update current day with live price
            current_day['close'] = spot_data['ltp']
            current_day['high'] = max(current_day['high'], spot_data['ltp'])
            current_day['low'] = min(current_day['low'], spot_data['ltp'])
        
        return jsonify({
            'symbol': symbol,
            'current_day': current_day,
            'previous_day': previous_day,
            'live_price': spot_data['ltp'],
            'timestamp': datetime.now().isoformat()
        })
        
    except ValidationError as e:
        return jsonify({'error': e.message}), 400
    except Exception as e:
        logger.error(f"Error fetching OHLC data for {symbol}: {e}")
        return jsonify({'error': str(e)}), 500

@api_blueprint.route('/underlying_ohlc/<symbol>', methods=['GET'])
def get_underlying_ohlc(symbol):
    """Return current + previous day OHLC for an underlying (no options).

    Uses quote for live price / intraday OHL and get_recent_daily_history for previous day.
    """
    try:
        symbol = Validators.validate_symbol(symbol)
        market_service = current_app.market_service
        kite_service = current_app.kite_api_service if hasattr(current_app, 'kite_api_service') else None
        if kite_service is None:
            from services.kite_api_service import kite_api_service as ks
            kite_service = ks

        # Spot/quote
        spot = market_service.get_spot_price_sync(symbol)

        # Recent history (two days) to derive previous day values (real data) with caching inside service
        history = kite_service.get_recent_daily_history(symbol, 2)
        previous_day = history[-2] if len(history) >= 2 else None
        if previous_day is None:
            # Fallback: treat quote ohlc as previous day's close if history unavailable (better than blank UI)
            q = market_service.get_spot_price_sync(symbol)
            ohlc = (q or {}).get('ohlc', {}) if isinstance(q, dict) else {}
            prev_close = ohlc.get('close') if isinstance(ohlc, dict) else None
            if prev_close is not None:
                previous_day = {
                    'date': datetime.now().date().isoformat(),
                    'open': ohlc.get('open') or prev_close,
                    'high': ohlc.get('high') or prev_close,
                    'low': ohlc.get('low') or prev_close,
                    'close': prev_close,
                    'volume': 0
                }

        # Accurate intraday OHLC for underlying using minute candles
        intraday = kite_service.get_underlying_intraday_ohlc(symbol)
        current_day = {
            'open': intraday.get('open') or spot.get('previous_close', 0),
            'high': intraday.get('high') or (spot.get('ltp', 0) or spot.get('spot_price', 0)),
            'low': intraday.get('low') or (spot.get('ltp', 0) or spot.get('spot_price', 0)),
            'close': intraday.get('close') or (spot.get('ltp', 0) or spot.get('spot_price', 0)),
            'volume': intraday.get('volume', 0)
        }

        return jsonify({
            'symbol': symbol,
            'current_day': current_day,
            'previous_day': previous_day,
            'live_price': spot.get('ltp', 0) or spot.get('spot_price', 0),
            'reference_price': spot.get('previous_close', 0),
            'timestamp': datetime.now().isoformat()
        })
    except ValidationError as e:
        return jsonify({'error': e.message}), 400
    except Exception as e:
        logger.error(f"Error in underlying_ohlc for {symbol}: {e}")
        return jsonify({'error': str(e)}), 500

# WebSocket statistics endpoint
@api_blueprint.route('/websocket/stats', methods=['GET'])
def get_websocket_stats():
    """Get WebSocket connection statistics"""
    try:
        websocket_service = current_app.websocket_service
        stats = websocket_service.get_subscription_stats()
        
        return jsonify(ResponseFormatter.success(
            data=stats,
            message="WebSocket statistics retrieved successfully"
        ))
        
    except Exception as e:
        logger.error(f"Error fetching WebSocket stats: {e}")
        return jsonify(ResponseFormatter.error("Failed to fetch WebSocket statistics")), 500

# Advanced analysis endpoints (based on your root app.py)
@api_blueprint.route('/advanced_option_analysis/<symbol>', methods=['GET'])
def get_advanced_option_analysis(symbol):
    """
    Get advanced option analysis with ITM/ATM/OTM classification
    Based on your root app.py advanced analysis endpoint
    """
    try:
        # Validate symbol
        symbol = Validators.validate_symbol(symbol)
        
        # Get and validate parameters
        expiry_date = request.args.get('expiry_date')
        if expiry_date:
            expiry_date = Validators.validate_expiry_date(expiry_date)
        
        # Get service instance
        option_service = current_app.option_service
        
        # Get advanced analysis data
        analysis_data = option_service.get_advanced_option_analysis(symbol, expiry_date)
        
        return jsonify(ResponseFormatter.success(
            data=analysis_data,
            message=f"Advanced option analysis for {symbol} retrieved successfully",
            meta={
                "symbol": symbol,
                "expiry_date": expiry_date,
                "analysis_type": "advanced",
                "timestamp": analysis_data.get('timestamp')
            }
        ))
        
    except ValidationError as e:
        return jsonify(ResponseFormatter.validation_error(e.field, e.message, e.value)), 400
    except Exception as e:
        logger.error(f"Error fetching advanced option analysis for {symbol}: {e}")
        return jsonify(ResponseFormatter.error(f"Failed to fetch advanced analysis for {symbol}")), 500

    # End of advanced analysis route

# ---------------- SMD KEY BUY endpoints (module-level) ---------------- #

def _is_market_hours(now_ist: datetime) -> bool:
    start = dtime(9, 0)
    end = dtime(16, 0)
    return start <= now_ist.time() <= end and now_ist.weekday() < 5

def _now_ist() -> datetime:
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

@api_blueprint.route('/smd-key-buy/calculate', methods=['POST'])
def smd_calculate():
    try:
        payload = request.get_json(silent=True) or {}
        symbol = Validators.validate_symbol(payload.get('symbol', 'NIFTY'))
        expiry = payload.get('expiry')
        smd_service = current_app.smd_service
        now_ist = _now_ist()
        allowed = _is_market_hours(now_ist)
        data = smd_service.calculate_prevday(symbol, expiry)
        return jsonify(ResponseFormatter.success(
            data={**data, 'status': 'ACTIVE' if allowed else 'RESTRICTED', 'now_ist': now_ist.isoformat()},
            message='SMD Key Buy calculated'
        ))
    except Exception as e:
        logger.error(f"SMD calculate error: {e}")
        return jsonify(ResponseFormatter.error('Failed to calculate SMD Key Buy')), 500

@api_blueprint.route('/smd-key-buy/save', methods=['POST'])
def smd_save():
    try:
        payload = request.get_json(silent=True) or {}
        symbol = Validators.validate_symbol(payload.get('symbol', 'NIFTY'))
        expiry = payload.get('expiry')
        smd_service = current_app.smd_service
        now_ist = _now_ist()
        if not _is_market_hours(now_ist):
            return jsonify(ResponseFormatter.error('Outside market hours; saving new Active entry is restricted')), 403
        data = smd_service.calculate_prevday(symbol, expiry)
        rec_id = smd_service.persist_snapshot(data)
        return jsonify(ResponseFormatter.success(data={**data, 'id': rec_id}, message='SMD Key Buy saved'))
    except Exception as e:
        logger.error(f"SMD save error: {e}")
        return jsonify(ResponseFormatter.error('Failed to save SMD Key Buy')), 500

@api_blueprint.route('/smd-key-buy/fetch', methods=['GET'])
def smd_fetch():
    try:
        hours = int(request.args.get('hours', 24))
        smd_service = current_app.smd_service
        items = smd_service.fetch_recent(within_hours=hours)
        return jsonify(ResponseFormatter.success(data=items, message='SMD Key Buy fetched'))
    except Exception as e:
        logger.error(f"SMD fetch error: {e}")
        return jsonify(ResponseFormatter.error('Failed to fetch SMD Key Buy')), 500

@api_blueprint.route('/smd-key-buy/purge', methods=['POST'])
def smd_purge():
    try:
        smd_service = current_app.smd_service
        smd_service.delete_older_than(24)
        return jsonify(ResponseFormatter.success(data={'ok': True}, message='SMD Key Buy purged'))
    except Exception as e:
        logger.error(f"SMD purge error: {e}")
        return jsonify(ResponseFormatter.error('Failed to purge SMD Key Buy')), 500

@api_blueprint.route('/sharpe_analysis/<symbol>', methods=['GET'])
def get_sharpe_analysis(symbol):
    """
    Get SHARPE logic analysis (your root app.py SHARPE feature)
    """
    try:
        # Validate symbol
        symbol = Validators.validate_symbol(symbol)
        
        # Get parameters
        expiry_date = request.args.get('expiry_date')
        
        # Get service instance
        option_service = current_app.option_service
        
        # Get advanced analysis and format for SHARPE logic
        analysis_data = option_service.get_advanced_option_analysis(symbol, expiry_date)
        
        # Format data for SHARPE logic display
        sharpe_data = {
            'symbol': symbol,
            'market_phase': analysis_data.get('market_phase'),
            'ohlc_analysis': analysis_data.get('ohlc_data'),
            'strike_analysis': {
                'itm_analysis': analysis_data['option_data']['itm_strikes'],
                'atm_analysis': analysis_data['option_data']['atm_strikes'],
                'otm_analysis': analysis_data['option_data']['otm_strikes']
            },
            'market_sentiment': analysis_data['aggregate_statistics']['market_sentiment'],
            'pcr_analysis': {
                'pcr_oi': analysis_data.get('pcr_oi'),
                'pcr_volume': analysis_data.get('pcr_volume')
            },
            'support_resistance': analysis_data.get('support_resistance'),
            'sharpe_score': option_service.calculate_sharpe_score(analysis_data),
            'recommendations': option_service.generate_sharpe_recommendations(analysis_data)
        }
        
        return jsonify(ResponseFormatter.success(
            data=sharpe_data,
            message=f"SHARPE analysis for {symbol} retrieved successfully"
        ))
        
    except ValidationError as e:
        return jsonify(ResponseFormatter.validation_error(e.field, e.message, e.value)), 400
    except Exception as e:
        logger.error(f"Error fetching SHARPE analysis for {symbol}: {e}")
        return jsonify(ResponseFormatter.error(f"Failed to fetch SHARPE analysis for {symbol}")), 500

# ---------------- Additional SHARP PRO Logic (Previous-day based) ---------------- #

def _compute_additional_sharp_pro_payload(symbol: str, expiry: str | None):
    """Shared compute for Additional SHARP PRO payload.

    Returns the full ASP payload dict or raises on error.
    """
    from services.kite_api_service import kite_api_service

    # 1) Previous-day underlying close
    hist = kite_api_service.get_recent_daily_history(symbol, 2)
    if not hist or len(hist) < 2:
        raise RuntimeError(f"Insufficient history for {symbol}")
    prev_day_close = float(hist[-2].get('close') or 0)
    if prev_day_close <= 0:
        raise RuntimeError(f"Previous day close unavailable for {symbol}")

    # 2) Full option chain (all strikes) for selected/nearest expiry
    chain = kite_api_service.get_option_chain(symbol, expiry, include_all_strikes=True)
    option_rows = chain.get('option_chain', []) if isinstance(chain, dict) else []
    if not option_rows:
        raise RuntimeError(f"No option chain for {symbol}")

    # Build strike -> row map
    strike_to_row = { float(r.get('strike_price')): r for r in option_rows if r.get('strike_price') is not None }
    strikes = sorted(strike_to_row.keys())
    if not strikes:
        raise RuntimeError("No strikes available")

    # 3) Determine strike interval (min positive diff near ATM)
    diffs = sorted({ round(abs(b - a)) for a, b in zip(strikes[:-1], strikes[1:]) if b > a })
    strike_interval = int(diffs[0]) if diffs else 50
    if strike_interval <= 0:
        strike_interval = 50

    # Helper to find nearest available strike
    def nearest_strike(target: float) -> float:
        return min(strikes, key=lambda s: abs(s - target))

    # 4) ATM derived from previous day spot close
    atm_prev = nearest_strike(prev_day_close)

    # Also provide ATM rounded to 50 and 100 for reference
    def round_to_nearest(x: float, step: int) -> float:
        try:
            return round(x / step) * step
        except Exception:
            return x
    atm_round_50 = nearest_strike(round_to_nearest(prev_day_close, 50))
    atm_round_100 = nearest_strike(round_to_nearest(prev_day_close, 100))

    # Extract prev close helper
    def prev_close_for(row: dict, side: str) -> float:
        if not isinstance(row, dict):
            return 0.0
        if side == 'CE':
            val = row.get('ce_prev_close')
            # Fallback to quote ohlc close (previous close) if present on CE
            if val is None:
                val = row.get('ce_close') or row.get('ce_ltp')
            return float(val or 0)
        else:
            val = row.get('pe_prev_close')
            if val is None:
                val = row.get('pe_close') or row.get('pe_ltp')
            return float(val or 0)

    # Compose step matrices
    def build_steps(kind: str):
        # kind: 'ITM' or 'OTM'
        steps = []
        for n in range(1, 11):
            if kind == 'ITM':
                ce_strike = atm_prev - n * strike_interval
                pe_strike = atm_prev + n * strike_interval
            else:  # OTM
                ce_strike = atm_prev + n * strike_interval
                pe_strike = atm_prev - n * strike_interval
            # Find nearest available strikes in case of gaps
            ce_s = nearest_strike(ce_strike)
            pe_s = nearest_strike(pe_strike)
            ce_row = strike_to_row.get(ce_s)
            pe_row = strike_to_row.get(pe_s)
            ce_pc = prev_close_for(ce_row, 'CE')
            pe_pc = prev_close_for(pe_row, 'PE')
            smd_val = round(((ce_pc or 0) + (pe_pc or 0)) / 2.0, 2)
            steps.append({
                'step': n,
                'ce_strike': ce_s,
                'pe_strike': pe_s,
                'ce_prev_close': ce_pc,
                'pe_prev_close': pe_pc,
                'smd': smd_val
            })
        return steps

    # ATM pair
    atm_row = strike_to_row.get(atm_prev)
    atm_ce_pc = prev_close_for(atm_row, 'CE')
    atm_pe_pc = prev_close_for(atm_row, 'PE')
    atm_smd = round(((atm_ce_pc or 0) + (atm_pe_pc or 0)) / 2.0, 2)

    itm_steps = build_steps('ITM')
    otm_steps = build_steps('OTM')

    summary = {
        'smd_atm': atm_smd,
        'smd_itm_step1': itm_steps[0]['smd'],
        'smd_itm_step3': itm_steps[2]['smd'],
        'smd_itm_step5': itm_steps[4]['smd'],
        'smd_otm_step1': otm_steps[0]['smd'],
        'smd_otm_step3': otm_steps[2]['smd'],
        'smd_otm_step5': otm_steps[4]['smd'],
        'avg_itm': round(sum(s['smd'] for s in itm_steps) / len(itm_steps), 2),
        'avg_otm': round(sum(s['smd'] for s in otm_steps) / len(otm_steps), 2)
    }

    return {
        'symbol': symbol,
        'expiry': chain.get('expiry'),
        'prev_day_spot_close': prev_day_close,
        'atm_from_prev_close': atm_prev,
        'strike_interval': strike_interval,
        'atm_round_50': atm_round_50,
        'atm_round_100': atm_round_100,
        'atm_pair': {
            'strike': atm_prev,
            'ce_prev_close': atm_ce_pc,
            'pe_prev_close': atm_pe_pc,
            'smd': atm_smd
        },
        'itm_steps': itm_steps,
        'otm_steps': otm_steps,
        'summary': summary,
        'timestamp': datetime.now().isoformat()
    }
@api_blueprint.route('/sharp-pro/additional', methods=['POST'])
def additional_sharp_pro():
    """Compute Additional SHARP PRO Logic using previous-day spot/ATM and per-option prev closes.

    Request JSON: { symbol: string, expiry?: string }
        Response: success payload with
      - prev_day_spot_close
      - atm_from_prev_close
      - strike_interval
      - atm_round_50, atm_round_100
            - matrices for ITM/ATM/OTM (10 steps) with CE/PE strikes, prev_close and SMD per step
            - summary SMD values (atm, itm_step1/3/5, otm_step1/3/5)
    """
    try:
        payload = request.get_json(silent=True) or {}
        symbol = Validators.validate_symbol(payload.get('symbol', 'NIFTY'))
        expiry = payload.get('expiry')

        result = _compute_additional_sharp_pro_payload(symbol, expiry)
        return jsonify(ResponseFormatter.success(data=result, message=f"Additional SHARP PRO computed for {symbol}"))
    except ValidationError as e:
        return jsonify(ResponseFormatter.validation_error(e.field, e.message, e.value)), 400
    except Exception as e:
        logger.error(f"Error in additional SHARP PRO for {payload if 'payload' in locals() else ''}: {e}")
        return jsonify(ResponseFormatter.error("Failed to compute Additional SHARP PRO")), 500

@api_blueprint.route('/sharp-pro/additional/batch', methods=['POST'])
def additional_sharp_pro_batch():
    """Batch compute Additional SHARP PRO for multiple symbols in one call.

    Request JSON: { symbols: string[], expiry?: string }
    Response: { results: { [symbol]: aspPayload }, errors: { [symbol]: { code, details } } }
    """
    try:
        payload = request.get_json(silent=True) or {}
        symbols = payload.get('symbols') or []
        expiry = payload.get('expiry')
        if not isinstance(symbols, list) or not symbols:
            return jsonify(ResponseFormatter.validation_error('symbols', 'symbols must be a non-empty array', symbols)), 400

        results = {}
        errors = {}
        for sym in symbols:
            try:
                s = Validators.validate_symbol(sym)
                results[s] = _compute_additional_sharp_pro_payload(s, expiry)
            except ValidationError as ve:
                errors[str(sym)] = {'code': 'VALIDATION_ERROR', 'details': {'field': ve.field, 'message': ve.message}}
            except Exception as e:
                errors[str(sym)] = {'code': 'COMPUTE_FAILED', 'details': {'exception': str(e)}}

        return jsonify(ResponseFormatter.success(data={'results': results, 'errors': errors}, message=f"ASP batch complete: {len(results)} ok, {len(errors)} errors"))
    except Exception as e:
        logger.error(f"Error in additional_sharp_pro_batch: {e}")
        return jsonify(ResponseFormatter.error('Failed to compute Additional SHARP PRO batch')), 500

@api_blueprint.route('/additional-sharp-pro', methods=['GET'])
def additional_sharp_pro_get():
    """GET alias for Additional SHARP PRO to support clients that use query params.

    Query params: ?symbol=XYZ&expiry=YYYY-MM-DD
    """
    try:
        symbol_param = request.args.get('symbol', 'NIFTY')
        symbol = Validators.validate_symbol(symbol_param)
        expiry = request.args.get('expiry')
        if expiry:
            expiry = Validators.validate_expiry_date(expiry)

        result = _compute_additional_sharp_pro_payload(symbol, expiry)
        return jsonify(ResponseFormatter.success(data=result, message=f"Additional SHARP PRO computed for {symbol}"))
    except ValidationError as e:
        return jsonify(ResponseFormatter.validation_error(e.field, e.message, e.value)), 400
    except Exception as e:
        logger.error(f"Error in additional_sharp_pro_get: {e}")
        return jsonify(ResponseFormatter.error("Failed to compute Additional SHARP PRO")), 500

def _calculate_sharpe_score(analysis_data: dict) -> float:
    """Calculate SHARPE score based on market conditions"""
    try:
        # Simple SHARPE scoring based on PCR and market sentiment
        pcr_oi = analysis_data.get('pcr_oi', 0)
        pcr_volume = analysis_data.get('pcr_volume', 0)
        
        # Normalize PCR values (ideal PCR around 1.0)
        pcr_score = 1 - abs(1.0 - (pcr_oi + pcr_volume) / 2)
        
        # Market sentiment multiplier
        sentiment = analysis_data['aggregate_statistics']['market_sentiment']
        sentiment_multiplier = {'BULLISH': 1.2, 'NEUTRAL': 1.0, 'BEARISH': 0.8}.get(sentiment, 1.0)
        
        return round(pcr_score * sentiment_multiplier * 100, 2)
        
    except Exception:
        return 50.0  # Default neutral score

def _generate_sharpe_recommendations(analysis_data: dict) -> list:
    """Generate SHARPE-based trading recommendations"""
    try:
        recommendations = []
        sentiment = analysis_data['aggregate_statistics']['market_sentiment']
        pcr_oi = analysis_data.get('pcr_oi', 0)
        
        if sentiment == 'BULLISH' and pcr_oi < 0.8:
            recommendations.append("Consider CALL buying on pullbacks")
            recommendations.append("Look for PUT selling opportunities")
        elif sentiment == 'BEARISH' and pcr_oi > 1.2:
            recommendations.append("Consider PUT buying on rallies")
            recommendations.append("Look for CALL selling opportunities")
        else:
            recommendations.append("Market is neutral - consider range-bound strategies")
            recommendations.append("Monitor for breakout signals")
            
        return recommendations
        
    except Exception:
        return ["Monitor market conditions closely"]

# Error handlers for the blueprint
@api_blueprint.errorhandler(404)
def api_not_found(error):
    """Handle 404 errors in API blueprint"""
    return jsonify(ResponseFormatter.not_found_error("API endpoint", request.path)), 404

@api_blueprint.errorhandler(500)
def api_internal_error(error):
    """Handle 500 errors in API blueprint"""
    logger.error(f"API Internal Error: {error}")
    return jsonify(ResponseFormatter.error("Internal API error")), 500
