"""
Error Handlers
Custom error handling for the Flask application
"""

import logging
from flask import jsonify, request
from werkzeug.exceptions import HTTPException

logger = logging.getLogger(__name__)

class ValidationError(Exception):
    """Custom validation error"""
    def __init__(self, field: str, message: str, value=None):
        self.field = field
        self.message = message
        self.value = value
        super().__init__(f"Validation error in {field}: {message}")

class APIException(Exception):
    """Custom API exception with status code"""
    
    def __init__(self, message: str, status_code: int = 500, error_code: str = None, details: dict = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or f"API_ERROR_{status_code}"
        self.details = details or {}

def register_error_handlers(app):
    """Register custom error handlers with the Flask app"""
    
    @app.errorhandler(ValidationError)
    def handle_validation_error(error):
        """Handle validation errors"""
        logger.warning(f"Validation error: {error.message} for field {error.field}")
        
        from utils.response_formatter import ResponseFormatter
        response = ResponseFormatter.validation_error(
            field=error.field,
            message=error.message,
            value=error.value
        )
        
        return jsonify(response), 400
    
    @app.errorhandler(404)
    def handle_not_found(error):
        """Handle 404 errors"""
        logger.info(f"404 error for path: {request.path}")
        
        from utils.response_formatter import ResponseFormatter
        response = ResponseFormatter.not_found_error(
            resource="endpoint",
            identifier=request.path
        )
        
        return jsonify(response), 404
    
    @app.errorhandler(500)
    def handle_internal_error(error):
        """Handle 500 Internal Server errors"""
        logger.error(f"500 error for path: {request.path}, error: {str(error)}")
        
        from utils.response_formatter import ResponseFormatter
        response = ResponseFormatter.error(
            message="Internal server error occurred",
            error_code="INTERNAL_SERVER_ERROR",
            details={"path": request.path} if app.debug else {},
            status_code=500
        )
        
        return jsonify(response), 500

def register_api_exception_handler(app):
    """Register handler for custom API exceptions"""
    
    @app.errorhandler(APIException)
    def handle_api_exception(error):
        """Handle custom API exceptions"""
        logger.error(f"API exception: {error.message}")
        
        from utils.response_formatter import ResponseFormatter
        response = ResponseFormatter.error(
            message=error.message,
            error_code=error.error_code,
            details=error.details,
            status_code=error.status_code
        )
        
        return jsonify(response), error.status_code

def register_request_logging(app):
    """Register request logging middleware"""
    
    @app.before_request
    def log_request_info():
        """Log request information for debugging"""
        if request.endpoint:
            logger.info(f"{request.method} {request.path} - {request.endpoint}")
            
            if request.json:
                logger.debug(f"Request JSON: {request.json}")
            
            if request.args:
                logger.debug(f"Request args: {dict(request.args)}")
