"""
Main Flask Application
Entry point for the trading platform backend
"""

# IMPORTANT: If using eventlet, monkey_patch must happen before importing anything else

import os
import logging
from flask import Flask, jsonify
from datetime import datetime, timedelta
from flask_socketio import SocketIO
from flask_cors import CORS

# Import configuration
from config.settings import Config

# Import API routes
from api.routes import api_blueprint

# Import services
from services.websocket_service import WebSocketService
from services.market_data_service import MarketDataService
from services.option_chain_service import OptionChainService
from services.smd_key_buy_service import SmdKeyBuyService
from services.kite_api_service import kite_api_service
from services.kite_token_service import kite_token_service
import threading
import time

# Import utilities
from utils.error_handlers import register_error_handlers, register_api_exception_handler, register_request_logging
# Ensure ORM models are imported so metadata is registered
from models import SmdKeyBuy  # noqa: F401

def create_app(config_name='development'):
    """Application factory pattern"""
    
    # Create Flask app
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_object(Config)
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO if not app.config['DEBUG'] else logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"Starting trading platform backend in {config_name} mode")
    
    # Initialize CORS for React frontend
    CORS(app, 
         origins='*',
         allow_headers=['Content-Type', 'Authorization'],
         methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
         supports_credentials=True)
    
    # Initialize SocketIO
    socketio = SocketIO(
        app,
        cors_allowed_origins='*',
        logger=True,
        engineio_logger=True,
        async_mode='eventlet' if _EVENTLET_AVAILABLE else 'threading',
        ping_interval=25,
        ping_timeout=60,
        max_http_buffer_size=10_000_000,
    allow_upgrades=False,
    )
    # Expose socketio on app for services
    app.socketio = socketio
    
    # Initialize services
    market_service = MarketDataService()
    option_service = OptionChainService()
    smd_service = SmdKeyBuyService()
    websocket_service = WebSocketService(socketio)
    
    # Store services in app context for access in routes
    app.market_service = market_service
    app.option_service = option_service
    app.websocket_service = websocket_service
    app.smd_service = smd_service
    app.kite_api_service = kite_api_service
    app.kite_token_service = kite_token_service
    
    # Register error handlers
    register_error_handlers(app)
    register_api_exception_handler(app)
    register_request_logging(app)
    
    # Register blueprints
    app.register_blueprint(api_blueprint, url_prefix='/api')

    # Start daily scheduler for SMD Key Buy persistence and purge
    def _run_smd_scheduler():
        last_run_date = None
        while True:
            try:
                # Compute IST time
                now_utc = datetime.utcnow()
                ist_now = now_utc + timedelta(hours=5, minutes=30)
                if ist_now.hour == 16 and ist_now.minute >= 5:
                    if last_run_date != ist_now.date():
                        logger.info("[SMD Scheduler] Running daily persist & purge at 16:05 IST")
                        try:
                            # Persist snapshots for a curated symbol set to avoid rate limits
                            from services.kite_api_service import kite_api_service
                            symbols_info = kite_api_service.get_all_symbols()
                            indices = symbols_info.get('indices', [])
                            stocks = symbols_info.get('stocks_with_options', [])[:100]  # cap to 100 to reduce load
                            commodities = symbols_info.get('commodities', [])
                            batch = list(dict.fromkeys(indices + stocks + commodities))
                            for sym in batch:
                                try:
                                    data = smd_service.calculate_prevday(sym)
                                    smd_service.persist_snapshot(data)
                                    time.sleep(0.2)
                                except Exception as e:
                                    logger.warning(f"[SMD Scheduler] Persist failed for {sym}: {e}")
                            # Purge items older than 24h
                            smd_service.delete_older_than(24)
                            logger.info("[SMD Scheduler] Completed persist & purge")
                            last_run_date = ist_now.date()
                        except Exception as e:
                            logger.error(f"[SMD Scheduler] Error: {e}")
                time.sleep(30)
            except Exception:
                time.sleep(30)

    try:
        t = threading.Thread(target=_run_smd_scheduler, daemon=True)
        t.start()
        logger.info("SMD daily scheduler started")
    except Exception as e:
        logger.error(f"Failed to start SMD scheduler: {e}")
    
    # Start Additional Sharp Pro background broadcaster
    try:
        from services.additional_sharp_pro_signal_service import start_signal_broadcaster
        start_signal_broadcaster(app)
        logger.info("Additional Sharp Pro signal broadcaster started")
    except Exception as e:
        logger.error(f"Failed to start ASP signal broadcaster: {e}")
    
    # Health check endpoint
    @app.route('/health')
    def health_check():
        """Health check endpoint"""
        from utils.response_formatter import ResponseFormatter
        
        services_status = {
            "market_data": {"healthy": True, "status": "operational"},
            "option_chain": {"healthy": True, "status": "operational"},
            "websocket": {"healthy": True, "status": "operational", 
                         "connected_clients": websocket_service.get_connected_clients_count()},
            "database": {"healthy": True, "status": "operational"}  # Placeholder
        }
        
        return jsonify(ResponseFormatter.health_check_response(services_status))
    
    # Root endpoint
    @app.route('/')
    def root():
        """Root endpoint"""
        from utils.response_formatter import ResponseFormatter
        
        return jsonify(ResponseFormatter.success(
            data={
                "service": "Trading Platform Backend API",
                "version": "1.0.0",
                "status": "operational",
                "endpoints": {
                    "health": "/health",
                    "api": "/api",
                    "websocket": "/socket.io"
                }
            },
            message="Trading Platform Backend API is running"
        ))
    
    logger.info("Flask application created successfully")
    return app, socketio

# Create app instance
app, socketio = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0')
    debug_mode = os.environ.get('DEBUG', 'True').lower() == 'true'
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                  Trading Platform Backend                   ║
║                        Starting...                          ║
╠══════════════════════════════════════════════════════════════╣
║  🚀 Server: http://{host}:{port}                              ║
║  📊 API: http://{host}:{port}/api                             ║
║  💹 WebSocket: ws://{host}:{port}/socket.io                   ║
║  ❤️  Health: http://{host}:{port}/health                      ║
║  🔧 Debug: {debug_mode}                                        ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    socketio.run(app, host=host, port=port, debug=debug_mode, use_reloader=False)
