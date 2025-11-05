"""
Transaction webhook endpoint for receiving and processing payment webhooks.

This module handles incoming webhook requests from payment processors like RazorPay,
validates the data, stores transactions, and triggers background processing with
proper idempotency handling.
"""
import asyncio
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel, Field
from typing import Optional
from core.db import get_db_client, DatabaseClient
from core.utils import (
    get_current_timestamp, 
    validate_transaction_data, 
    ResponseFormatter,
    timing_decorator
)
from helper.transaction_processor import process_transaction_background

router = APIRouter()


class TransactionWebhookRequest(BaseModel):
    """
    Pydantic model for incoming transaction webhook requests.
    
    This model validates the structure and types of incoming webhook data
    according to the API specification.
    """
    transaction_id: str = Field(..., min_length=5, description="Unique transaction identifier")
    source_account: str = Field(..., min_length=3, description="Source account identifier")  
    destination_account: str = Field(..., min_length=3, description="Destination account identifier")
    amount: float = Field(..., gt=0, description="Transaction amount (must be positive)")
    currency: str = Field(..., min_length=3, max_length=3, description="Currency code (e.g., USD, INR)")


class TransactionWebhookResponse(BaseModel):
    """Response model for webhook acknowledgment."""
    status: str = Field(description="Processing status")
    message: str = Field(description="Response message")
    timestamp: str = Field(description="Response timestamp")


@router.post(
    "/webhooks/transactions",
    response_model=TransactionWebhookResponse,
    status_code=202,
    tags=["Webhooks"],
    summary="Receive transaction webhook",
    description="Accepts transaction webhooks from payment processors and triggers background processing"
)
@timing_decorator
async def receive_transaction_webhook(
    request: TransactionWebhookRequest,
    background_tasks: BackgroundTasks,
    db_client: DatabaseClient = Depends(get_db_client)
):
    """
    Handle incoming transaction webhook requests.
    
    This endpoint:
    1. Validates the incoming transaction data
    2. Checks for duplicate transactions (idempotency)
    3. Stores the transaction with PROCESSING status
    4. Triggers background processing
    5. Returns HTTP 202 Accepted within 500ms
    
    Args:
        request: The validated transaction webhook request
        background_tasks: FastAPI background tasks for async processing
        db_client: Database client dependency
        
    Returns:
        TransactionWebhookResponse: Acknowledgment response
        
    Raises:
        HTTPException: If validation fails or database errors occur
    """
    try:
        # Convert request to dictionary for processing
        transaction_data = request.dict()
        
        # Validate transaction data structure
        is_valid, error_message = validate_transaction_data(transaction_data)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_message)
        
        # Check if transaction already exists (idempotency check)
        # Use webhook path timeout (3 seconds) for fast response
        existing_transaction = await db_client.get_transaction(
            request.transaction_id,
            timeout=3.0  # Fast lookup for webhook acknowledgment
        )
        
        if existing_transaction:
            # Transaction already exists, return appropriate message based on status
            transaction_status = existing_transaction.get("status", "UNKNOWN")
            
            if transaction_status == "PROCESSED":
                message = f"Transaction {request.transaction_id} already received and fully processed"
            elif transaction_status == "PROCESSING":
                message = f"Transaction {request.transaction_id} is already being processed"
            else:
                message = f"Transaction {request.transaction_id} already exists with status: {transaction_status}"
            
            return ResponseFormatter.accepted(message)
        
        # Prepare transaction record for database
        transaction_record = {
            **transaction_data,
            "status": "PROCESSING",
            "created_at": get_current_timestamp(),
            "processed_at": None
        }
        
        # Store transaction in database with webhook timeout
        await db_client.create_transaction(
            transaction_record,
            timeout=3.0  # Fast insert for webhook acknowledgment
        )
        
        # Add background processing task
        background_tasks.add_task(
            process_transaction_background,
            request.transaction_id,
            db_client
        )
        
        # Return immediate acknowledgment
        return ResponseFormatter.accepted(
            f"Transaction {request.transaction_id} accepted for processing"
        )
    
    except asyncio.TimeoutError:
        # Database operation timed out
        print(f"Database timeout for transaction {request.transaction_id}")
        raise HTTPException(
            status_code=503,
            detail="Database operation timed out. Please retry the request."
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
        
    except Exception as e:
        # Handle unexpected errors
        print(f"Unexpected error processing webhook for {request.transaction_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error while processing webhook: {str(e)}"
        )