"""
Configuration module for Transaction Webhook Service.

This module provides centralized configuration management for the FastAPI application,
including environment variables, database settings, and service configurations.
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    Follows the 12-factor app methodology for configuration management.
    All sensitive data should be stored in environment variables.
    """
    
    # Application Settings
    APP_NAME: str = "Transaction Webhook Service"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # API Settings
    API_V1_PREFIX: str = "/api/v1"
    API_V2_PREFIX: str = "/api/v2"
    
    # CORS Settings
    CORS_ORIGINS: list = ["*"]  # In production, specify allowed origins
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list = ["*"]
    CORS_ALLOW_HEADERS: list = ["*"]
    
    # Supabase Configuration
    SUPABASE_URL: str
    SUPABASE_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = None
    
    # Database Table Names
    TRANSACTIONS_TABLE: str = "transactions"
    USERS_TABLE: str = "users"
    
    # Background Processing Settings
    PROCESSING_DELAY_SECONDS: int = 30
    MAX_RETRY_ATTEMPTS: int = 3
    WEBHOOK_TIMEOUT_SECONDS: float = 0.5  # 500ms response requirement
    
    # Security Settings
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Deployment Settings
    DEPLOYED_URL: Optional[str] = None
    
    class Config:
        """Pydantic configuration class."""
        env_file = ".env"
        case_sensitive = True
        extra = "allow"  # Allow extra fields in .env


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """
    Dependency function to get settings instance.
    
    Returns:
        Settings: The application settings instance
    """
    return settings