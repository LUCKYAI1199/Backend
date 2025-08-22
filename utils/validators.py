"""
Validation Utilities
Input validation for API endpoints
"""

import re
from datetime import datetime, timedelta
from typing import Any, List, Dict

class ValidationError(Exception):
    """Custom validation error"""
    def __init__(self, field: str, message: str, value: Any = None):
        self.field = field
        self.message = message
        self.value = value
        super().__init__(f"Validation error in {field}: {message}")

class Validators:
    """Collection of validation utilities"""
    
    # Valid symbols for the trading platform
    VALID_SYMBOLS = {
        # NSE/BSE Indices
        'NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY', 'SENSEX',
        'NIFTYIT', 'NIFTYPHARMA', 'NIFTYBANK', 'NIFTYFMCG', 'NIFTYAUTO',
        # NSE/BSE Stocks
        'TATAMOTORS', 'HDFCBANK', 'SBIN', 'AXISBANK', 'ICICIBANK', 
        'RELIANCE', 'INFY', 'TCS', 'HINDUNILVR', 'ASIANPAINT',
        # MCX Commodities
        'COPPER', 'CRUDEOIL', 'CRUDEOILM', 'GOLD', 'GOLDM', 
        'NATGASMINI', 'NATURALGAS', 'SILVER', 'SILVERM', 'ZINC'
    }
    
    # Valid timeframes for historical data
    VALID_TIMEFRAMES = {
        '1min', '3min', '5min', '10min', '15min', '30min', 
        '1hour', '2hour', '4hour', '1day', '1week', '1month'
    }
    
    @staticmethod
    def validate_symbol(symbol: str) -> str:
        """Validate trading symbol"""
        if not symbol:
            raise ValidationError("symbol", "Symbol is required")
        
        symbol = symbol.upper().strip()
        
        # Remove strict validation and let Kite API handle symbol validation
        # The hardcoded list was too restrictive for all 225+ stocks
        if not re.match(r'^[A-Z0-9&-]+$', symbol):
            raise ValidationError("symbol", "Invalid symbol format. Must contain only letters, numbers, and hyphens", symbol)
        
        return symbol
    
    @staticmethod
    def validate_expiry_date(expiry: str) -> str:
        """Validate expiry date format and value"""
        if not expiry:
            raise ValidationError("expiry", "Expiry date is required")
        
        # Check date format (YYYY-MM-DD)
        date_pattern = r'^\d{4}-\d{2}-\d{2}$'
        if not re.match(date_pattern, expiry):
            raise ValidationError("expiry", "Expiry date must be in YYYY-MM-DD format", expiry)
        
        try:
            expiry_date = datetime.strptime(expiry, '%Y-%m-%d').date()
            today = datetime.now().date()
            
            # Check if expiry is too far in the past (allow some flexibility)
            if expiry_date < today - timedelta(days=30):
                raise ValidationError("expiry", "Expiry date too far in the past", expiry)
            
            # Check if expiry is too far in the future (max 1 year)
            max_date = today + timedelta(days=365)
            if expiry_date > max_date:
                raise ValidationError("expiry", "Expiry date cannot be more than 1 year in the future", expiry)
            
            return expiry
            
        except ValueError:
            raise ValidationError("expiry", "Invalid date format", expiry)
    
    @staticmethod
    def validate_timeframe(timeframe: str) -> str:
        """Validate timeframe"""
        if not timeframe:
            raise ValidationError("timeframe", "Timeframe is required")
        
        timeframe = timeframe.lower().strip()
        
        if timeframe not in Validators.VALID_TIMEFRAMES:
            raise ValidationError("timeframe", f"Invalid timeframe. Valid timeframes: {', '.join(list(Validators.VALID_TIMEFRAMES)[:5])}", timeframe)
        
        return timeframe
