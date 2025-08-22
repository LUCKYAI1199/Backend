# Trading Platform Backend

A comprehensive Flask-based backend API for the SMD Trading Platform, providing real-time option chain data, market analysis, and WebSocket connectivity for React frontend.

## 🏗️ Architecture Overview

backend/
├── app.py                 # Main Flask application entry point
├── requirements.txt       # Python dependencies
├── README.md             # This file
├── config/
│   ├── __init__.py
│   └── settings.py       # Configuration management
├── api/
│   ├── __init__.py
│   └── routes.py         # REST API endpoints
├── services/
│   ├── __init__.py
│   ├── option_chain_service.py    # Option chain data logic
│   ├── market_data_service.py     # Real-time market data
│   └── websocket_service.py       # WebSocket connection management
├── utils/
│   ├── __init__.py
│   ├── response_formatter.py      # API response standardization
│   ├── validators.py              # Input validation utilities
│   └── error_handlers.py          # Error handling and logging
└── models/
    └── __init__.py                # Future database models

## 🚀 Features

### Core API Endpoints

- **Symbol Management

: Get available trading symbols (NIFTY, BANKNIFTY, etc.)

- **Expiry Dates: Fetch available option expiry dates for symbols

- **Spot Prices: Real-time spot price data with change calculations
- **Option Chain: Complete option chain data with CE/PE strikes
- **Dashboard Metrics: PCR ratios, OI analysis, max pain calculation
- **Historical Data: OHLC data with configurable timeframes
- **Market Status: Live market open/close status

### Real-time Features

- **WebSocket Support: Real-time data streaming to React frontend
- **Live Price Updates: Continuous spot price and option price updates
- **Market Status Broadcasting: Real-time market phase updates
- **Client Connection Management: Multi-client subscription handling

### Data Services

- **Option Chain Service: Handles option data fetching and caching
- **Market Data Service: Manages real-time and historical market data
- **WebSocket Service: Manages real-time client connections and data streaming

### Utilities

- **Response Formatting: Standardized API response structure
- **Input Validation: Comprehensive request validation
- **Error Handling: Centralized error management and logging
- **CORS Support: Configured for React frontend at localhost:3000

## 🔧 Installation & Setup

### Prerequisites

- Python 3.8+
- pip (Python package manager)
- Node.js (for frontend)

### Backend Installation

1. **Navigate to backend directory:

   ```bash
   cd "d:\live pro\backend"
   ```

2. **Create virtual environment (recommended):

   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   # source venv/bin/activate  # Linux/Mac
   ```

3. **Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. **Set environment variables (optional):

   ```bash
   # Create .env file
   DEBUG=True
   PORT=5000
   HOST=0.0.0.0
   FRONTEND_URL=http://localhost:3000
   ```

5. **Run the backend:

   ```bash
   python app.py
   ```

The backend will start at `http://localhost:5000`

## 📡 API Endpoints

### Core Endpoints

#### Health Check

```http
GET /health
GET /api/health
```

#### Symbols

```http
GET /api/symbols                           # Get all available symbols
GET /api/expiries/{symbol}                 # Get expiry dates for symbol  
GET /api/spot_price/{symbol}               # Get current spot price
```

#### Option Chain

```http
GET /api/option_chain?symbol={symbol}&expiry={expiry}
GET /api/dashboard_data?symbol={symbol}&expiry={expiry}
```

#### Market Data

```http
GET /api/market-status                     # Current market status
GET /api/historical-data/{symbol}          # Historical OHLC data
GET /api/ohlc_data/{symbol}               # Current day OHLC
```

#### WebSocket

```http
GET /api/websocket/stats                   # Connection statistics
WebSocket: ws://localhost:5000/socket.io   # Real-time connection
```

### Response Format

All API responses follow a standardized format:

```json
{
  "success": true,
  "message": "Success message",
  "timestamp": "2025-01-17T12:00:00.000Z",
  "data": { ... },
  "meta": { 
    "symbol": "NIFTY",
    "pagination": { ... }
  }
}
```

Error responses:

```json

{
  "success": false,
  "message": "Error description",
  "timestamp": "2025-01-17T12:00:00.000Z",
  "error": {
    "code": "VALIDATION_ERROR",
    "details": { ... }
  }
}
```

## 🌐 WebSocket Events

### Client → Server Events

```javascript
// Subscribe to real-time symbol updates
socket.emit('subscribe_symbol', { symbol: 'NIFTY' });

// Get option chain data
socket.emit('get_option_chain', { symbol: 'NIFTY', expiry: '2024-01-25' });

// Get dashboard data
socket.emit('get_dashboard_data', { symbol: 'NIFTY', expiry: '2024-01-25' });

// Unsubscribe from symbol
socket.emit('unsubscribe_symbol', { symbol: 'NIFTY' });

// Ping server
socket.emit('ping');
```

### Server → Client Events

```javascript
// Real-time symbol price updates
socket.on('symbol_update', (data) => {
  console.log('Price update:', data);
});

// Option chain data response
socket.on('option_chain_data', (data) => {
  console.log('Option chain:', data);
});

// Market status updates
socket.on('market_status', (data) => {
  console.log('Market status:', data);
});

// Connection status
socket.on('connection_status', (data) => {
  console.log('Connected:', data);
});

// Error notifications
socket.on('error', (error) => {
  console.error('WebSocket error:', error);
});
```

## 🔄 Frontend Integration

### React Frontend Connection

The backend is specifically configured to work with the React frontend:

1. **CORS Configuration: Allows requests from `http://localhost:3000`
2. **WebSocket CORS: Enables WebSocket connections from React app
3. **API Compatibility: Endpoints match existing frontend `ApiService` calls
4. **Response Format: Compatible with frontend TypeScript interfaces

### Frontend ApiService Integration

The backend endpoints are designed to work with the existing frontend `ApiService`:

```typescript
// These frontend calls are supported:
ApiService.getExpiries(symbol)           // → /api/expiries/{symbol}
ApiService.getSpotPrice(symbol)          // → /api/spot_price/{symbol}  
ApiService.getOptionChain(symbol, expiry) // → /api/option_chain
ApiService.getDashboardData(symbol)      // → /api/dashboard_data
```

## 🛠️ Development

### Code Structure

- **Services: Business logic separated into service classes
- **Routes: Clean API endpoint definitions with validation
- **Utilities: Reusable validation, formatting, and error handling
- **Configuration: Centralized app configuration management

### Adding New Features

1. **New Service: Add to `services/` directory
2. **New Route: Add to `api/routes.py` with proper validation
3. **New Utility: Add to `utils/` for reusable functions
4. **Update Config: Modify `config/settings.py` if needed

### Testing

```bash
# Run tests (when implemented)
pytest

# Test specific endpoint
curl http://localhost:5000/api/health

# Test WebSocket connection
# Use browser dev tools or WebSocket testing tool
```

## 🔧 Configuration

### Environment Variables

Create `.env` file in backend directory:

```env
# Application settings
DEBUG=True
PORT=5000
HOST=0.0.0.0

# Frontend connection
FRONTEND_URL=http://localhost:3000

# API settings
API_TIMEOUT=30
RATE_LIMIT_PER_MINUTE=100

# WebSocket settings
WEBSOCKET_TIMEOUT=60
MAX_CLIENTS=100

# Kite API (for live trading - optional)
# KITE_API_KEY=your_api_key
# KITE_API_SECRET=your_api_secret
# KITE_ACCESS_TOKEN=your_access_token
```

### Configuration Files

Main configuration in `config/settings.py`:

- Flask app settings
- CORS configuration  
- WebSocket settings
- API timeouts and limits
- Trading symbols list

## 📊 Data Sources

### Current Implementation

- **Mock Data: Generates realistic option chain and price data
- **Cached Responses: 30-second caching for performance
- **Fallback System: Graceful degradation when services unavailable

### Future Integration

- **Kite Connect API: For live market data (requires API credentials)
- **Database Storage: Historical data persistence
- **External APIs: Additional data sources integration

## 🚀 Deployment

### Development

```bash
python app.py
```

### Production (example)

```bash
# Using gunicorn
pip install gunicorn
gunicorn -w 4 -k gevent --worker-connections 1000 app:app

# Using Docker
docker build -t trading-backend .
docker run -p 5000:5000 trading-backend
```

## 📝 API Documentation

Full API documentation available at:

- **Health Check: `http://localhost:5000/health`
- **API Root: `http://localhost:5000/api`
- **WebSocket: `ws://localhost:5000/socket.io`

## 🤝 Frontend-Backend Communication

### Data Flow

1. **React Frontend makes API calls to Flask backend
2. **Backend Services process requests and fetch/generate data
3. **WebSocket Service provides real-time updates
4. **Response Formatters ensure consistent API responses
5. **Error Handlers manage failures gracefully

### Real-time Architecture

- **HTTP REST APIs for request-response operations
- **WebSocket connections for real-time data streaming
- **Event-driven updates for live price feeds
- **Connection management for multiple client support

## 🔒 Security Features

- **Input Validation: All inputs validated before processing
- **CORS Protection: Restricted to frontend origin
- **Error Sanitization: Sensitive information filtered from responses
- **Rate Limiting: Prevention of API abuse
- **Connection Limits: WebSocket connection management

## 📈 Performance

- **Response Caching: 30-second cache for expensive operations
- **Async Support: Non-blocking operations where possible
- **Connection Pooling: Efficient WebSocket management
- **Data Optimization: Minimal payload sizes
- **Error Recovery: Graceful handling of service failures

## 🔍 Monitoring

- **Health Checks: Built-in system health monitoring
- **WebSocket Stats: Connection and subscription metrics
- **Error Logging: Comprehensive error tracking
- **Performance Metrics: Response time monitoring

---

## 🎯 Ready for React Frontend

This backend is fully configured and ready to connect with the React frontend at `http://localhost:3000`. All endpoints match the existing frontend `ApiService` calls, ensuring seamless integration.

**Start the backend:

```bash
cd "d:\live pro\backend"
python app.py
```

**Expected output:

╔══════════════════════════════════════════════════════════════╗
║                  Trading Platform Backend                   ║
║                        Starting...                          ║
╠══════════════════════════════════════════════════════════════╣
║  🚀 Server: [http://localhost:5000](http://localhost:5000)

║  📊 API: [http://localhost:5000/api](http://localhost:5000/api)

║  💹 WebSocket: ws://localhost:5000/socket.io

║  ❤️ Health: [http://localhost:5000/health](http://localhost:5000/health)
                   ║
║  🔧 Debug: True                             ║
╚══════════════════════════════════════════════════════════════╝

The React frontend can now successfully connect and communicate with this backend for all trading platform functionality.
