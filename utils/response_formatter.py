"""
Response Formatter Utility
Standardizes API response format
"""

from typing import Any, Dict, Optional, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class ResponseFormatter:
    """Utility class for formatting API responses"""
    
    @staticmethod
    def success(data: Any = None, message: str = "Success", meta: Optional[Dict] = None) -> Dict:
        """Format successful response"""
        response = {
            "success": True,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "data": data
        }
        
        if meta:
            response["meta"] = meta
            
        return response
    
    @staticmethod
    def error(message: str = "An error occurred", error_code: Optional[str] = None, 
              details: Optional[Dict] = None, status_code: int = 500) -> Dict:
        """Format error response"""
        response = {
            "success": False,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "error": {
                "code": error_code or "INTERNAL_ERROR",
                "details": details or {}
            }
        }
        
        return response
    
    @staticmethod
    def option_chain_response(option_data: Dict, symbol: str, expiry: str) -> Dict:
        """Format option chain specific response"""
        try:
            # Extract key metrics
            metrics = {
                "spot_price": option_data.get("spot_price"),
                "total_ce_oi": option_data.get("total_ce_oi", 0),
                "total_pe_oi": option_data.get("total_pe_oi", 0),
                "pcr_oi": option_data.get("pcr_oi", 0),
                "atm_strike": option_data.get("atm_strike"),
                "max_pain": option_data.get("max_pain")
            }
            
            meta = {
                "symbol": symbol,
                "expiry": expiry,
                "data_timestamp": option_data.get("timestamp"),
                "total_strikes": len(option_data.get("option_chain", [])),
                "metrics": metrics
            }
            
            return ResponseFormatter.success(
                data=option_data.get("option_chain", []),
                message=f"Option chain data for {symbol} expiry {expiry}",
                meta=meta
            )
            
        except Exception as e:
            logger.error(f"Error formatting option chain response: {e}")
            return ResponseFormatter.error(
                message="Failed to format option chain response",
                details={"symbol": symbol, "expiry": expiry}
            )
    
    @staticmethod
    def market_data_response(market_data: Dict, symbol: str) -> Dict:
        """Format market data specific response"""
        try:
            meta = {
                "symbol": symbol,
                "data_timestamp": market_data.get("timestamp"),
                "market_status": "open"  # This would be determined from market hours
            }
            
            return ResponseFormatter.success(
                data=market_data,
                message=f"Market data for {symbol}",
                meta=meta
            )
            
        except Exception as e:
            logger.error(f"Error formatting market data response: {e}")
            return ResponseFormatter.error(
                message="Failed to format market data response",
                details={"symbol": symbol}
            )
    
    @staticmethod
    def validation_error(field: str, message: str, value: Any = None) -> Dict:
        """Format validation error response"""
        details = {
            "field": field,
            "message": message,
            "value": value
        }
        
        return ResponseFormatter.error(
            message=f"Validation error: {message}",
            error_code="VALIDATION_ERROR",
            details=details,
            status_code=400
        )
    
    @staticmethod
    def not_found_error(resource: str, identifier: str = None) -> Dict:
        """Format not found error response"""
        message = f"{resource} not found"
        if identifier:
            message += f" with identifier: {identifier}"
            
        return ResponseFormatter.error(
            message=message,
            error_code="NOT_FOUND",
            details={"resource": resource, "identifier": identifier},
            status_code=404
        )
    
    @staticmethod
    def health_check_response(services_status: Dict) -> Dict:
        """Format health check response"""
        all_healthy = all(status.get("healthy", False) for status in services_status.values())
        
        return {
            "success": True,
            "healthy": all_healthy,
            "timestamp": datetime.now().isoformat(),
            "services": services_status,
            "version": "1.0.0"
        }
