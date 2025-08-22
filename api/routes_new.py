"""
API Routes for Trading Platform Backend
Handles all REST API endpoints with proper service integration
"""

from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
import logging

# Import utilities
from utils.response_formatter import ResponseFormatter
from utils.validators import Validators, ValidationError
from utils.error_handlers import APIException

logger = logging.getLogger(__name__)

# Create blueprint
api_blueprint = Blueprint('api', __name__)

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

# Symbol-related endpoints
@api_blueprint.route('/symbols', methods=['GET'])
def get_symbols():
    """Get available symbols"""
    try:
        symbols = {
            "indices": ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX"],
            "stocks": ["RELIANCE", "TCS", "HDFC", "INFY", "ICICIBANK"]
        }
        
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
        
        # Fetch spot price (this is an async function, but we'll call it synchronously for now)
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            spot_data = loop.run_until_complete(market_service.get_spot_price(symbol))
        finally:
            loop.close()
        
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
