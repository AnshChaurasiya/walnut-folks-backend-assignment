"""
Transaction webhook endpoint for receiving and processing payment webhooks.

This module handles incoming webhook requests from payment processors like RazorPay,
validates the data, stores transactions, and triggers background processing with
proper idempotency handling.
"""
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
        existing_transaction = await db_client.get_transaction(request.transaction_id)
        
        if existing_transaction:
            # Transaction already exists, return accepted without reprocessing
            return ResponseFormatter.accepted(
                f"Transaction {request.transaction_id} already received and processed"
            )
        
        # Prepare transaction record for database
        transaction_record = {
            **transaction_data,
            "status": "PROCESSING",
            "created_at": get_current_timestamp(),
            "processed_at": None
        }
        
        # Store transaction in database
        created_transaction = await db_client.create_transaction(transaction_record)
        
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
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
        
    except Exception as e:
        # Handle unexpected errors
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error while processing webhook: {str(e)}"
        )