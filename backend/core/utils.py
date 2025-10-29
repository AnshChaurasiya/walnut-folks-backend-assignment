"""
Utility functions and helpers for the Transaction Webhook Service.

This module contains common utility functions, decorators, and helpers
that are used across different parts of the application.
"""
import time
import hashlib
import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Callable
from functools import wraps


def get_current_timestamp() -> str:
    """
    Get the current UTC timestamp in ISO format.
    
    Returns:
        str: Current UTC timestamp in ISO 8601 format
    """
    return datetime.now(timezone.utc).isoformat()


def generate_idempotency_key(transaction_data: Dict[str, Any]) -> str:
    """
    Generate an idempotency key from transaction data.
    
    This ensures that duplicate transactions can be detected and handled
    appropriately without processing them multiple times.
    
    Args:
        transaction_data: The transaction data dictionary
        
    Returns:
        str: SHA256 hash of the transaction data
    """
    # Sort the dictionary to ensure consistent hashing
    sorted_data = str(sorted(transaction_data.items()))
    return hashlib.sha256(sorted_data.encode()).hexdigest()


def timing_decorator(func: Callable) -> Callable:
    """
    Decorator to measure function execution time.
    
    Args:
        func: The function to measure
        
    Returns:
        Callable: Wrapped function with timing
    """
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            execution_time = time.time() - start_time
            print(f"{func.__name__} executed in {execution_time:.3f} seconds")
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            print(f"{func.__name__} failed in {execution_time:.3f} seconds: {str(e)}")
            raise
    
    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            print(f"{func.__name__} executed in {execution_time:.3f} seconds")
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            print(f"{func.__name__} failed in {execution_time:.3f} seconds: {str(e)}")
            raise
    
    return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper


def validate_transaction_data(data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """
    Validate transaction data structure and required fields.
    
    Args:
        data: Transaction data to validate
        
    Returns:
        tuple: (is_valid, error_message)
    """
    required_fields = [
        "transaction_id",
        "source_account", 
        "destination_account",
        "amount",
        "currency"
    ]
    
    # Check if all required fields are present
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return False, f"Missing required fields: {', '.join(missing_fields)}"
    
    # Validate transaction_id format
    transaction_id = data.get("transaction_id", "")
    if not isinstance(transaction_id, str) or len(transaction_id) < 5:
        return False, "transaction_id must be a string with at least 5 characters"
    
    # Validate amount
    amount = data.get("amount")
    if not isinstance(amount, (int, float)) or amount <= 0:
        return False, "amount must be a positive number"
    
    # Validate currency
    currency = data.get("currency", "")
    if not isinstance(currency, str) or len(currency) != 3:
        return False, "currency must be a 3-character string (e.g., 'USD', 'INR')"
    
    # Validate account IDs
    source_account = data.get("source_account", "")
    destination_account = data.get("destination_account", "")
    
    if not isinstance(source_account, str) or len(source_account) < 3:
        return False, "source_account must be a string with at least 3 characters"
    
    if not isinstance(destination_account, str) or len(destination_account) < 3:
        return False, "destination_account must be a string with at least 3 characters"
    
    if source_account == destination_account:
        return False, "source_account and destination_account cannot be the same"
    
    return True, None


def format_transaction_response(transaction: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format transaction data for API response.
    
    Args:
        transaction: Raw transaction data from database
        
    Returns:
        Dict: Formatted transaction data for API response
    """
    return {
        "transaction_id": transaction.get("transaction_id"),
        "source_account": transaction.get("source_account"),
        "destination_account": transaction.get("destination_account"),
        "amount": transaction.get("amount"),
        "currency": transaction.get("currency"),
        "status": transaction.get("status"),
        "created_at": transaction.get("created_at"),
        "processed_at": transaction.get("processed_at")
    }


def sanitize_input(data: str) -> str:
    """
    Sanitize user input to prevent injection attacks.
    
    Args:
        data: Input string to sanitize
        
    Returns:
        str: Sanitized string
    """
    if not isinstance(data, str):
        return str(data)
    
    # Remove potentially dangerous characters
    dangerous_chars = ["<", ">", "&", "\"", "'", ";", "(", ")", "[", "]", "{", "}"]
    sanitized = data
    
    for char in dangerous_chars:
        sanitized = sanitized.replace(char, "")
    
    return sanitized.strip()


class ResponseFormatter:
    """Helper class for formatting consistent API responses."""
    
    @staticmethod
    def success(data: Any = None, message: str = "Success") -> Dict[str, Any]:
        """
        Format success response.
        
        Args:
            data: Response data
            message: Success message
            
        Returns:
            Dict: Formatted success response
        """
        response = {
            "status": "success",
            "message": message,
            "timestamp": get_current_timestamp()
        }
        
        if data is not None:
            response["data"] = data
            
        return response
    
    @staticmethod
    def error(message: str, code: str = "INTERNAL_ERROR", details: Any = None) -> Dict[str, Any]:
        """
        Format error response.
        
        Args:
            message: Error message
            code: Error code
            details: Additional error details
            
        Returns:
            Dict: Formatted error response
        """
        response = {
            "status": "error",
            "error": {
                "code": code,
                "message": message
            },
            "timestamp": get_current_timestamp()
        }
        
        if details is not None:
            response["error"]["details"] = details
            
        return response
    
    @staticmethod
    def accepted(message: str = "Request accepted for processing") -> Dict[str, Any]:
        """
        Format accepted response for async processing.
        
        Args:
            message: Acceptance message
            
        Returns:
            Dict: Formatted accepted response
        """
        return {
            "status": "ACCEPTED",
            "message": message,
            "timestamp": get_current_timestamp()
        }