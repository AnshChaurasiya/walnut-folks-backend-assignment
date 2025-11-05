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

# Timeout configuration for different operation types
WEBHOOK_PATH_TIMEOUT = 3.0  # Fast timeout for webhook acknowledgment path (3 seconds)
STATUS_QUERY_TIMEOUT = 8.0  # Reasonable timeout for status queries (8 seconds)
DEFAULT_TIMEOUT = 10.0  # Default timeout for general operations
# No timeout for background processing - can take as long as needed


class DatabaseClient:
    """
    Supabase database client wrapper with async support.
    
    Provides a centralized interface for all database operations
    with proper error handling, connection management, and timeout protection.
    """
    
    def __init__(self):
        """Initialize the database client with timeout protection."""
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
    
    async def create_transaction(
        self, 
        transaction_data: Dict[str, Any], 
        timeout: Optional[float] = WEBHOOK_PATH_TIMEOUT
    ) -> Dict[str, Any]:
        """
        Create a new transaction record in the database.
        
        Args:
            transaction_data: Transaction data to insert
            timeout: Optional timeout in seconds (None = no timeout for background operations)
            
        Returns:
            Dict containing the created transaction record
            
        Raises:
            asyncio.TimeoutError: If timeout is set and operation exceeds it
            RuntimeError: If the database operation fails
        """
        try:
            client = self.get_service_client()  # Use service client for write operations
            
            # Execute with optional timeout protection
            if timeout:
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        lambda: client.table(settings.TRANSACTIONS_TABLE).insert(transaction_data).execute()
                    ),
                    timeout=timeout
                )
            else:
                # No timeout - for background operations that can take as long as needed
                response = await asyncio.to_thread(
                    lambda: client.table(settings.TRANSACTIONS_TABLE).insert(transaction_data).execute()
                )
            
            if response.data:
                return response.data[0]
            else:
                raise RuntimeError("Failed to create transaction record")
                
        except asyncio.TimeoutError:
            print(f"Database timeout creating transaction (>{timeout}s)")
            raise
        except Exception as e:
            print(f"Error creating transaction: {str(e)}")
            raise
    
    async def get_transaction(
        self, 
        transaction_id: str, 
        timeout: Optional[float] = STATUS_QUERY_TIMEOUT
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve a transaction by its ID.
        
        Args:
            transaction_id: The unique transaction identifier
            timeout: Optional timeout in seconds (None = no timeout)
            
        Returns:
            Dict containing transaction data or None if not found or timeout occurs
        """
        try:
            client = self.get_service_client()  # Use service client for consistency
            
            # Execute with optional timeout protection
            if timeout:
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        lambda: client.table(settings.TRANSACTIONS_TABLE)
                            .select("*")
                            .eq("transaction_id", transaction_id)
                            .execute()
                    ),
                    timeout=timeout
                )
            else:
                # No timeout - wait as long as needed
                response = await asyncio.to_thread(
                    lambda: client.table(settings.TRANSACTIONS_TABLE)
                        .select("*")
                        .eq("transaction_id", transaction_id)
                        .execute()
                )
            
            return response.data[0] if response.data else None
            
        except asyncio.TimeoutError:
            print(f"Database timeout fetching transaction {transaction_id} (>{timeout}s)")
            return None
        except Exception as e:
            print(f"Error fetching transaction {transaction_id}: {str(e)}")
            return None
    
    async def update_transaction_status(
        self, 
        transaction_id: str, 
        status: str, 
        processed_at: Optional[str] = None,
        use_timeout: bool = False,
        max_retries: int = 3
    ) -> bool:
        """
        Update transaction status and processed timestamp with retry logic.
        
        Args:
            transaction_id: The unique transaction identifier
            status: New status ("PROCESSING" or "PROCESSED")
            processed_at: Timestamp when processing completed
            use_timeout: Whether to enforce timeout (False for background operations)
            max_retries: Number of retry attempts on failure
            
        Returns:
            bool: True if update was successful, False otherwise
        """
        return await self._execute_update_with_retry(
            transaction_id, status, processed_at, use_timeout, max_retries
        )
    
    async def _execute_update_with_retry(
        self,
        transaction_id: str,
        status: str,
        processed_at: Optional[str],
        use_timeout: bool,
        max_retries: int
    ) -> bool:
        """Internal method to execute update with retry logic."""
        for attempt in range(max_retries):
            try:
                success = await self._execute_single_update(
                    transaction_id, status, processed_at, use_timeout
                )
                if success:
                    return True
                    
                print(f"No rows updated for transaction {transaction_id}")
                return False
                
            except asyncio.TimeoutError:
                timeout_val = DEFAULT_TIMEOUT if use_timeout else "N/A"
                print(f"Database timeout updating transaction {transaction_id} (>{timeout_val}s), attempt {attempt + 1}/{max_retries}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s, 4s
                    continue
                return False
            except Exception as e:
                print(f"Error updating transaction {transaction_id}: {str(e)}, attempt {attempt + 1}/{max_retries}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    continue
                return False
        
        return False
    
    async def _execute_single_update(
        self,
        transaction_id: str,
        status: str,
        processed_at: Optional[str],
        use_timeout: bool
    ) -> bool:
        """Internal method to execute a single update operation."""
        client = self.get_service_client()
        update_data = {"status": status}
        
        if processed_at:
            update_data["processed_at"] = processed_at
        
        # Create the operation function
        def db_operation():
            return client.table(settings.TRANSACTIONS_TABLE)\
                .update(update_data)\
                .eq("transaction_id", transaction_id)\
                .execute()
        
        # Execute with optional timeout
        if use_timeout:
            response = await asyncio.wait_for(
                asyncio.to_thread(db_operation),
                timeout=DEFAULT_TIMEOUT
            )
        else:
            # No timeout - wait as long as needed (for background processing)
            response = await asyncio.to_thread(db_operation)
        
        return len(response.data) > 0

# Global database client instance
db_client = DatabaseClient()


def get_db_client() -> DatabaseClient:
    """
    Dependency function to get database client instance.
    
    Returns:
        DatabaseClient: The database client instance
    """
    return db_client