"""
Health check endpoint for the Transaction Webhook Service.

This module provides a simple health check endpoint that returns the service
status and current timestamp, useful for monitoring and load balancer health checks.
"""
from fastapi import APIRouter
from core.utils import get_current_timestamp, ResponseFormatter

router = APIRouter()


@router.get("/", tags=["Health Check"])
async def health_check():
    """
    Health check endpoint that returns service status.
    
    Returns:
        dict: Service status and current timestamp
        
    Example response:
        {
            "status": "HEALTHY",
            "current_time": "2024-01-15T10:30:00Z"
        }
    """
    return {
        "status": "HEALTHY",
        "current_time": get_current_timestamp()
    }