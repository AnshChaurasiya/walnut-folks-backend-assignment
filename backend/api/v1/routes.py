from fastapi import APIRouter
from .health_check import router as health_router
from .webhook_transaction import router as webhook_router
from .transaction_status import router as transaction_router

# Create the main v1 API router
api_v1_router = APIRouter()


def initialize_v1_routes(app_router: APIRouter) -> None:
    """
    Initialize and register all v1 API routes.
    
    This function follows the routing architecture pattern by centralizing
    all route registrations in a single place, making it easy to manage
    and organize endpoints.
    
    Args:
        app_router: The main application router to register routes with
    """
    
    # =============================================================================
    # HEALTH CHECK ENDPOINTS
    # =============================================================================
    app_router.include_router(
        health_router,
        tags=["Health Check"]
    )
    
    # =============================================================================
    # WEBHOOK ENDPOINTS
    # =============================================================================
    app_router.include_router(
        webhook_router,
        prefix="/v1",
        tags=["Webhooks"]
    )
    
    # =============================================================================
    # TRANSACTION MANAGEMENT ENDPOINTS
    # =============================================================================
    app_router.include_router(
        transaction_router,
        prefix="/v1",
        tags=["Transactions"]
    )
