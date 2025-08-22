"""
WebSocket Service
Handles real-time WebSocket connections for the trading platform
Based on your comprehensive root app.py WebSocket implementation
"""

import logging
import json
import threading
import time
from datetime import datetime
from typing import Dict, List, Set, Optional
from flask_socketio import SocketIO, emit, disconnect

logger = logging.getLogger(__name__)

class WebSocketService:
    """Service for handling WebSocket connections and real-time data"""
    
    def __init__(self, socketio: SocketIO):
        self.socketio = socketio
        self.connected_clients: Set[str] = set()
        self.client_subscriptions: Dict[str, Set[str]] = {}
        self.symbol_subscriptions: Dict[str, Set[str]] = {}  # symbol -> set of client_ids
        self.real_time_enabled = False
        self.update_thread = None
        
        # All supported symbols (from your root app.py)
        self.INDEX_SYMBOLS = ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY', 'SENSEX']
        self.STOCK_SYMBOLS = [
            'TATAMOTORS', 'HDFCBANK', 'SBIN', 'AXISBANK', 'ICICIBANK', 'RELIANCE', 'INFY', 'TCS', 'HINDUNILVR',
            'ASIANPAINT', 'ONGC', 'NTPC', 'JSWSTEEL', 'BHARTIARTL', 'HCLTECH', 'MARUTI', 'ADANIPORTS', 'SUNPHARMA',
            'UPL', 'LT', 'JSWENERGY', 'BIOCON', 'PHOENIXLTD', 'NATIONALUM', 'HAL', 'ABFRL', 'CONCOR', 'IEX',
            'UNOMINDA', 'SAIL', 'LICHSGFIN', 'BDL'
        ]
        self.MCX_COMMODITIES = [
            'COPPER', 'CRUDEOIL', 'CRUDEOILM', 'GOLD', 'GOLDM', 
            'NATGASMINI', 'NATURALGAS', 'SILVER', 'SILVERM', 'ZINC'
        ]
        self.ALL_SYMBOLS = self.INDEX_SYMBOLS + self.STOCK_SYMBOLS + self.MCX_COMMODITIES
        
        # Register event handlers
        self._register_handlers()
        
        # Start real-time update thread
        self._start_real_time_updates()
        
        logger.info("WebSocketService initialized")
    
    def _register_handlers(self):
        """Register WebSocket event handlers (from your root app.py)"""
        
        @self.socketio.on('connect')
        def handle_connect():
            """Handle client connection"""
            try:
                client_id = self._get_client_id()
                self.connected_clients.add(client_id)
                self.client_subscriptions[client_id] = set()
                
                logger.info(f"🔗 Client connected: {client_id}")
                
                # Send welcome message
                emit('connection_status', {
                    'status': 'connected',
                    'client_id': client_id,
                    'timestamp': datetime.now().isoformat(),
                    'message': 'Connected to trading platform'
                })
                
            except Exception as e:
                logger.error(f"Error handling connection: {e}")
                emit('error', {'message': 'Connection failed'})
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            """Handle client disconnection"""
            try:
                client_id = self._get_client_id()
                
                logger.info(f"❌ Client disconnected: {client_id}")
                
                if client_id in self.connected_clients:
                    self.connected_clients.remove(client_id)
                
                # Remove client from all symbol subscriptions
                for symbol in list(self.symbol_subscriptions.keys()):
                    if client_id in self.symbol_subscriptions[symbol]:
                        self.symbol_subscriptions[symbol].discard(client_id)
                        if not self.symbol_subscriptions[symbol]:
                            del self.symbol_subscriptions[symbol]
                
                # Remove client subscriptions
                if client_id in self.client_subscriptions:
                    del self.client_subscriptions[client_id]
                
            except Exception as e:
                logger.error(f"Error handling disconnection: {e}")
        
        @self.socketio.on('subscribe_symbol')
        def handle_subscribe_symbol(data):
            """Subscribe client to real-time updates for a symbol"""
            try:
                client_id = self._get_client_id()
                symbol = data.get('symbol', '').upper()
                
                if symbol and symbol in self.ALL_SYMBOLS:
                    # Add to client subscriptions
                    if client_id not in self.client_subscriptions:
                        self.client_subscriptions[client_id] = set()
                    self.client_subscriptions[client_id].add(symbol)
                    
                    # Add to symbol subscriptions
                    if symbol not in self.symbol_subscriptions:
                        self.symbol_subscriptions[symbol] = set()
                    self.symbol_subscriptions[symbol].add(client_id)
                    
                    logger.info(f"📡 Client {client_id} subscribed to {symbol}")
                    
                    emit('subscription_status', {
                        'symbol': symbol, 
                        'status': 'subscribed',
                        'timestamp': datetime.now().isoformat()
                    })
                    
                    # Send immediate data
                    self._send_immediate_data(symbol, client_id)
                    
                else:
                    emit('subscription_error', {'error': f'Invalid symbol: {symbol}'})
                    
            except Exception as e:
                logger.error(f"Error in subscribe_symbol: {e}")
                emit('error', {'message': 'Subscription failed'})
        
        @self.socketio.on('unsubscribe_symbol')
        def handle_unsubscribe_symbol(data):
            """Unsubscribe client from real-time updates for a symbol"""
            try:
                client_id = self._get_client_id()
                symbol = data.get('symbol', '').upper()
                
                # Remove from client subscriptions
                if client_id in self.client_subscriptions:
                    self.client_subscriptions[client_id].discard(symbol)
                
                # Remove from symbol subscriptions
                if symbol in self.symbol_subscriptions:
                    self.symbol_subscriptions[symbol].discard(client_id)
                    if not self.symbol_subscriptions[symbol]:
                        del self.symbol_subscriptions[symbol]
                
                logger.info(f"📡 Client {client_id} unsubscribed from {symbol}")
                
                emit('subscription_status', {
                    'symbol': symbol, 
                    'status': 'unsubscribed',
                    'timestamp': datetime.now().isoformat()
                })
                
            except Exception as e:
                logger.error(f"Error in unsubscribe_symbol: {e}")
                emit('error', {'message': 'Unsubscription failed'})
        
        @self.socketio.on('request_live_data')
        def handle_live_data_request(data):
            """Handle request for immediate live data"""
            try:
                client_id = self._get_client_id()
                symbol = data.get('symbol', '').upper()
                
                if symbol in self.ALL_SYMBOLS:
                    self._send_immediate_data(symbol, client_id)
                else:
                    emit('live_data_error', {'error': f'Invalid symbol: {symbol}'})
                    
            except Exception as e:
                logger.error(f"Error in request_live_data: {e}")
                emit('error', {'message': 'Live data request failed'})
        
        @self.socketio.on('ping')
        def handle_ping():
            """Handle ping request"""
            emit('pong', {'timestamp': datetime.now().isoformat()})
    
    def _get_client_id(self) -> str:
        """Get unique client ID"""
        from flask import request
        return request.sid
    
    def _send_immediate_data(self, symbol: str, client_id: str):
        """Send immediate data to a specific client"""
        try:
            # Get current data for the symbol
            data = self._get_symbol_live_data(symbol)
            
            self.socketio.emit('live_data_update', {
                'symbol': symbol,
                'data': data,
                'timestamp': datetime.now().isoformat()
            }, room=client_id)
            
        except Exception as e:
            logger.error(f"Error sending immediate data: {e}")
    
    def _get_symbol_live_data(self, symbol: str) -> dict:
        """Get live data for a symbol using real services, with safe fallback."""
        try:
            from flask import current_app
            
            # Try to get real data from services if we have app context
            try:
                if hasattr(current_app, 'option_service'):
                    option_service = current_app.option_service
                    market_service = current_app.market_service
                    
                    # Live quote and real OHLC
                    spot = market_service.get_spot_price_sync(symbol)
                    ohlc = market_service.get_ohlc_data(symbol)
                    spot_price = spot.get('ltp') or spot.get('spot_price') or 0
                    change = spot.get('change', 0)
                    change_percent = spot.get('change_percent', 0)
                    
                    # Market phase (best-effort)
                    market_phase_data = option_service._get_market_phase_data(symbol)
                    
                    return {
                        'spot_price': spot_price,
                        'change': change,
                        'change_percent': change_percent,
                        'market_phase': market_phase_data.get('market_phase', 'MARKET_HOURS'),
                        'ohlc_data': {
                            'open': ohlc.get('open', 0),
                            'high': ohlc.get('high', 0),
                            'low': ohlc.get('low', 0),
                            'close': ohlc.get('close', 0),
                            'volume': ohlc.get('volume', 0)
                        },
                        'volume': ohlc.get('volume', spot.get('volume', 0)),
                        'timestamp': spot.get('timestamp', datetime.now().isoformat())
                    }
            except RuntimeError:
                # Working outside application context, use mock data
                pass
            
            # Fallback mock data
            return self._generate_mock_live_data(symbol)
            
        except Exception as e:
            logger.error(f"Error getting symbol live data: {e}")
            return self._generate_mock_live_data(symbol)
    
    def _generate_mock_live_data(self, symbol: str) -> dict:
        """Generate mock live data for a symbol"""
        mock_prices = {
            'NIFTY': 24150.0,
            'BANKNIFTY': 51500.0,
            'FINNIFTY': 23850.0,
            'MIDCPNIFTY': 12500.0,
            'SENSEX': 79800.0
        }
        
        base_price = mock_prices.get(symbol, 24150.0)
        change = base_price * 0.002  # 0.2% change
        
        return {
            'spot_price': base_price,
            'change': change,
            'change_percent': 0.2,
            'market_phase': 'MARKET_HOURS',
            'ohlc_data': {
                'open': base_price * 1.001,
                'high': base_price * 1.005,
                'low': base_price * 0.995,
                'close': base_price,
                'volume': 125000
            },
            'volume': 125000,
            'timestamp': datetime.now().isoformat()
        }
    
    def _start_real_time_updates(self):
        """Start background thread for real-time updates (from your root app.py)"""
        try:
            self.real_time_enabled = True
            self.update_thread = threading.Thread(target=self._broadcast_real_time_updates, daemon=True)
            self.update_thread.start()
            logger.info("Real-time update thread started")
            
        except Exception as e:
            logger.error(f"Error starting real-time updates: {e}")
    
    def _broadcast_real_time_updates(self):
        """Background function to broadcast real-time updates to subscribed clients"""
        while self.real_time_enabled:
            try:
                if not self.symbol_subscriptions:
                    time.sleep(10)  # No subscriptions, wait longer
                    continue
                
                # Update each subscribed symbol
                for symbol, client_ids in self.symbol_subscriptions.items():
                    if client_ids:  # Only if there are subscribers
                        live_data = self._get_symbol_live_data(symbol)
                        
                        # Broadcast to all subscribed clients
                        self.socketio.emit('real_time_update', {
                            'symbol': symbol,
                            'data': live_data,
                            'timestamp': datetime.now().isoformat()
                        })
                        
                        logger.debug(f"📊 Broadcasting {symbol} data to {len(client_ids)} clients")
                
                # Wait 10 seconds before next update (your root app.py interval)
                time.sleep(10)
                
            except Exception as e:
                logger.error(f"Error in real-time broadcast: {e}")
                time.sleep(10)
    
    def stop_real_time_updates(self):
        """Stop real-time updates"""
        self.real_time_enabled = False
        if self.update_thread:
            self.update_thread.join(timeout=5)
        logger.info("Real-time updates stopped")
    
    def get_connected_clients_count(self) -> int:
        """Get number of connected clients"""
        return len(self.connected_clients)
    
    def get_subscription_stats(self) -> Dict:
        """Get subscription statistics"""
        symbol_counts = {}
        total_subscriptions = 0
        
        for symbol, client_ids in self.symbol_subscriptions.items():
            symbol_counts[symbol] = len(client_ids)
            total_subscriptions += len(client_ids)
        
        return {
            'connected_clients': len(self.connected_clients),
            'total_subscriptions': total_subscriptions,
            'active_symbols': len(self.symbol_subscriptions),
            'symbol_counts': symbol_counts,
            'timestamp': datetime.now().isoformat()
        }
    
    def broadcast_market_status(self, status_data: dict):
        """Broadcast market status to all connected clients"""
        try:
            self.socketio.emit('market_status', {
                'status': status_data,
                'timestamp': datetime.now().isoformat()
            })
            logger.info(f"Broadcasting market status to {len(self.connected_clients)} clients")
            
        except Exception as e:
            logger.error(f"Error broadcasting market status: {e}")
    
    def broadcast_symbol_update(self, symbol: str, data: dict):
        """Broadcast specific symbol update to subscribed clients"""
        try:
            if symbol in self.symbol_subscriptions and self.symbol_subscriptions[symbol]:
                self.socketio.emit('symbol_update', {
                    'symbol': symbol,
                    'data': data,
                    'timestamp': datetime.now().isoformat()
                })
                logger.debug(f"Broadcasting {symbol} update to {len(self.symbol_subscriptions[symbol])} clients")
                
        except Exception as e:
            logger.error(f"Error broadcasting symbol update: {e}")

    def emit_test_signal(self):
        """Emit a test signal to all connected clients"""
        try:
            test_signal = {
                'ts': int(time.time()),
                'event': 'TEST',
                'symbol': 'NIFTY',
                'price': 23450.50,
                'side': 'LONG',
                'strategy': 'TEST',
                'key': 'ATM',
                'note': 'Test signal for WebSocket connectivity'
            }
            
            self.socketio.emit('signal', test_signal)
            self.socketio.emit('message', test_signal)
            logger.info(f"📡 Emitted test signal to {len(self.connected_clients)} clients")
            
        except Exception as e:
            logger.error(f"Error emitting test signal: {e}")

    def emit_smd_signal(self, signal_data: dict):
        """Emit SMD trading signal to all connected clients"""
        try:
            self.socketio.emit('signal', signal_data)
            self.socketio.emit('message', signal_data)
            logger.info(f"📡 Emitted SMD signal: {signal_data.get('event')} for {signal_data.get('symbol')}")
            
        except Exception as e:
            logger.error(f"Error emitting SMD signal: {e}")

    def get_supported_symbols(self) -> list:
        """Get list of all supported symbols"""
        return self.ALL_SYMBOLS
