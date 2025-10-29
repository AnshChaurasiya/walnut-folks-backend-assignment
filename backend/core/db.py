"""
Database connection and client management for Supabase.

This module provides a centralized way to manage database connections,
initialize Supabase clients, and handle database operations with proper
error handling and connection pooling.
"""
import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from supabase import create_client, Client
from core.config import get_settings

settings = get_settings()


class DatabaseClient:
    """
    Supabase database client wrapper with async support.
    
    Provides a centralized interface for all database operations
    with proper error handling and connection management.
    """
    
    def __init__(self):
        """Initialize the database client."""
        self._client: Optional[Client] = None
        self._service_client: Optional[Client] = None
    
    def get_client(self) -> Client:
        """
        Get the regular Supabase client for standard operations.
        
        Returns:
            Client: Supabase client instance
        """
        if not self._client:
            self._client = create_client(
                settings.SUPABASE_URL,
                settings.SUPABASE_KEY
            )
        return self._client
    
    def get_service_client(self) -> Client:
        """
        Get the service role client for admin operations.
        
        Returns:
            Client: Supabase service role client instance
        """
        if not self._service_client and settings.SUPABASE_SERVICE_ROLE_KEY:
            self._service_client = create_client(
                settings.SUPABASE_URL,
                settings.SUPABASE_SERVICE_ROLE_KEY
            )
        return self._service_client or self.get_client()
    
    async def create_transaction(self, transaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new transaction record in the database.
        
        Args:
            transaction_data: Transaction data to insert
            
        Returns:
            Dict containing the created transaction record
            
        Raises:
            Exception: If the database operation fails
        """
        try:
            client = self.get_service_client()  # Use service client for write operations
            response = client.table(settings.TRANSACTIONS_TABLE).insert(transaction_data).execute()
            
            if response.data:
                return response.data[0]
            else:
                raise Exception("Failed to create transaction record")
                
        except Exception as e:
            print(f"Error creating transaction: {str(e)}")
            raise
    
    async def get_transaction(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a transaction by its ID.
        
        Args:
            transaction_id: The unique transaction identifier
            
        Returns:
            Dict containing transaction data or None if not found
        """
        try:
            client = self.get_service_client()  # Use service client for consistency
            response = client.table(settings.TRANSACTIONS_TABLE)\
                           .select("*")\
                           .eq("transaction_id", transaction_id)\
                           .execute()
            
            return response.data[0] if response.data else None
            
        except Exception as e:
            print(f"Error fetching transaction {transaction_id}: {str(e)}")
            return None
    
    async def update_transaction_status(
        self, 
        transaction_id: str, 
        status: str, 
        processed_at: Optional[str] = None
    ) -> bool:
        """
        Update transaction status and processed timestamp.
        
        Args:
            transaction_id: The unique transaction identifier
            status: New status ("PROCESSING" or "PROCESSED")
            processed_at: Timestamp when processing completed
            
        Returns:
            bool: True if update was successful, False otherwise
        """
        try:
            client = self.get_service_client()  # Use service client for write operations
            update_data = {"status": status}
            
            if processed_at:
                update_data["processed_at"] = processed_at
            
            response = client.table(settings.TRANSACTIONS_TABLE)\
                           .update(update_data)\
                           .eq("transaction_id", transaction_id)\
                           .execute()
            
            return len(response.data) > 0
            
        except Exception as e:
            print(f"Error updating transaction {transaction_id}: {str(e)}")
            return False

# Global database client instance
db_client = DatabaseClient()


def get_db_client() -> DatabaseClient:
    """
    Dependency function to get database client instance.
    
    Returns:
        DatabaseClient: The database client instance
    """
    return db_client