"""
Transaction status query endpoint.

This module provides endpoints to query the status and details of transactions
that have been processed through the webhook service.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional
from core.db import get_db_client, DatabaseClient
from core.utils import format_transaction_response, ResponseFormatter

router = APIRouter()


class TransactionStatusResponse(BaseModel):
    """Response model for transaction status queries."""
    transaction_id: str = Field(description="Unique transaction identifier")
    source_account: str = Field(description="Source account identifier")
    destination_account: str = Field(description="Destination account identifier")
    amount: float = Field(description="Transaction amount")
    currency: str = Field(description="Currency code")
    status: str = Field(description="Processing status (PROCESSING or PROCESSED)")
    created_at: str = Field(description="Transaction creation timestamp")
    processed_at: Optional[str] = Field(description="Processing completion timestamp")


@router.get(
    "/transactions/{transaction_id}",
    response_model=TransactionStatusResponse,
    tags=["Transactions"],
    summary="Get transaction status",
    description="Retrieve the current status and details of a specific transaction"
)
async def get_transaction_status(
    transaction_id: str,
    db_client: DatabaseClient = Depends(get_db_client)
):
    """
    Retrieve transaction status and details by transaction ID.
    
    Args:
        transaction_id: The unique transaction identifier
        db_client: Database client dependency
        
    Returns:
        TransactionStatusResponse: Transaction details and status
        
    Raises:
        HTTPException: If transaction is not found or database error occurs
    """
    try:
        # Fetch transaction from database
        transaction = await db_client.get_transaction(transaction_id)
        
        if not transaction:
            raise HTTPException(
                status_code=404,
                detail=f"Transaction {transaction_id} not found"
            )
        
        # Format and return transaction data
        return format_transaction_response(transaction)
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
        
    except Exception as e:
        # Handle unexpected errors
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error while fetching transaction: {str(e)}"
        )