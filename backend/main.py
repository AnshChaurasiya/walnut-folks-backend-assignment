"""
Main FastAPI application for Transaction Webhook Service.

This is the entry point for the FastAPI application that handles transaction
webhooks with proper routing, middleware, and error handling configuration.
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
import uvicorn
import time

from core.config import get_settings
from api.v1.routes import initialize_v1_routes

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager for startup and shutdown events.
    
    Args:
        app: FastAPI application instance
    """
    # Startup
    print(f"🚀 Starting {settings.APP_NAME} v{settings.VERSION}")
    print(f"🔧 Debug mode: {settings.DEBUG}")
    yield
    # Shutdown
    print("👋 Shutting down Transaction Webhook Service")


# Create FastAPI application instance
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="Production-ready transaction webhook service with background processing",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
)


# Response time middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """
    Middleware to add response time headers and ensure sub-500ms responses.
    
    Args:
        request: The incoming request
        call_next: The next middleware/endpoint in the chain
        
    Returns:
        Response with timing headers
    """
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    
    # Add response time header
    response.headers["X-Process-Time"] = str(process_time)
    
    # Log slow responses (webhook should be under 500ms)
    if process_time > settings.WEBHOOK_TIMEOUT_SECONDS:
        print(f"⚠️  Slow response: {process_time:.3f}s for {request.url.path}")
    
    return response


# Global exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handle Pydantic validation errors with detailed error messages.
    
    Args:
        request: The request that caused the error
        exc: The validation exception
        
    Returns:
        JSON response with validation error details
    """
    return JSONResponse(
        status_code=422,
        content={
            "status": "error",
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": exc.errors()
            },
            "timestamp": time.time()
        },
    )


@app.exception_handler(500)
async def internal_server_error_handler(request: Request, exc: Exception):
    """
    Handle internal server errors with proper logging.
    
    Args:
        request: The request that caused the error
        exc: The exception that occurred
        
    Returns:
        JSON response with error information
    """
    print(f"💥 Internal server error on {request.url.path}: {str(exc)}")
    
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An internal server error occurred"
            },
            "timestamp": time.time()
        },
    )


# Initialize API routes
initialize_v1_routes(app)

# Health check endpoint at root
@app.get("/", tags=["Health Check"])
async def root_health_check():
    """
    Root health check endpoint.
    
    Returns:
        dict: Service status and information
    """
    return {
        "status": "HEALTHY",
        "service": settings.APP_NAME,
        "version": settings.VERSION,
        "current_time": time.time()
    }


if __name__ == "__main__":
    """Run the application with Uvicorn when executed directly."""
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="info" if not settings.DEBUG else "debug"
    )