# app/api/payment_transaction_routes.py
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional
from datetime import datetime
import logging

from app.models.payment_method import PaymentTransaction, PaymentTransactionCreate, PaymentTransactionUpdate
from app.db.database import execute_query, execute_insert, execute_update, execute_delete

router = APIRouter(prefix="/api/v1/payment_transactions", tags=["PAYMENT TRANSACTIONS"])


logger = logging.getLogger("ocpp.payment_transactions")

@router.get("/", response_model=List[PaymentTransaction])
async def get_payment_transactions(
    company_id: Optional[int] = Query(None, description="Filter by company ID"),
    site_id: Optional[int] = Query(None, description="Filter by site ID"),
    charger_id: Optional[int] = Query(None, description="Filter by charger ID"),
    driver_id: Optional[int] = Query(None, description="Filter by driver ID"),
    session_id: Optional[int] = Query(None, description="Filter by session ID"),
    payment_method_id: Optional[int] = Query(None, description="Filter by payment method ID"),
    status: Optional[str] = Query(None, description="Filter by transaction status"),
    start_date: Optional[datetime] = Query(None, description="Filter by start date (from)"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date (to)"),
    limit: int = Query(100, description="Limit number of results"),
    offset: int = Query(0, description="Offset for pagination")
):
    """Get a list of payment transactions with optional filtering."""
    try:
        query = "SELECT * FROM PaymentTransactions"
        params = []
        
        # Build WHERE clause for filters
        filters = []
        
        if company_id is not None:
            filters.append("PaymentTransactionCompanyId = ?")
            params.append(company_id)
            
        if site_id is not None:
            filters.append("PaymentTransactionSiteId = ?")
            params.append(site_id)
            
        if charger_id is not None:
            filters.append("PaymentTransactionChargerId = ?")
            params.append(charger_id)
            
        if driver_id is not None:
            filters.append("PaymentTransactionDriverId = ?")
            params.append(driver_id)
            
        if session_id is not None:
            filters.append("PaymentTransactionSessionId = ?")
            params.append(session_id)
            
        if payment_method_id is not None:
            filters.append("PaymentTransactionMethodUsed = ?")
            params.append(payment_method_id)
            
        if status is not None:
            filters.append("PaymentTransactionStatus = ?")
            params.append(status)
            
        if start_date is not None:
            filters.append("PaymentTransactionDateTime >= ?")
            params.append(start_date.isoformat())
            
        if end_date is not None:
            filters.append("PaymentTransactionDateTime <= ?")
            params.append(end_date.isoformat())
            
        if filters:
            query += f" WHERE {' AND '.join(filters)}"
            
        query += " ORDER BY PaymentTransactionDateTime DESC LIMIT ? OFFSET ?"
        params.append(limit)
        params.append(offset)
        
        transactions = execute_query(query, tuple(params))
        return transactions
    except Exception as e:
        logger.error(f"Error getting payment transactions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/stripe/{stripe_intent_id}", response_model=PaymentTransaction)
async def get_transaction_by_stripe_intent(stripe_intent_id: str):
    """Get payment transaction by Stripe payment intent ID."""
    try:
        transaction = execute_query(
            "SELECT * FROM PaymentTransactions WHERE PaymentTransactionStripeIntentId = ?", 
            (stripe_intent_id,)
        )
        
        if not transaction:
            raise HTTPException(status_code=404, detail=f"Payment transaction with Stripe intent ID {stripe_intent_id} not found")
            
        return transaction[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting payment transaction by Stripe intent {stripe_intent_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/{transaction_id}", response_model=PaymentTransaction)
async def get_payment_transaction(transaction_id: int):
    """Get details of a specific payment transaction by ID."""
    try:
        transaction = execute_query(
            "SELECT * FROM PaymentTransactions WHERE PaymentTransactionId = ?", 
            (transaction_id,)
        )
        
        if not transaction:
            raise HTTPException(status_code=404, detail=f"Payment transaction with ID {transaction_id} not found")
            
        return transaction[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting payment transaction {transaction_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.post("/", response_model=PaymentTransaction, status_code=201)
async def create_payment_transaction(transaction: PaymentTransactionCreate):
    """Create a new payment transaction."""
    try:
        # Validate referenced entities exist
        company = execute_query(
            "SELECT 1 FROM Companies WHERE CompanyId = ?", 
            (transaction.PaymentTransactionCompanyId,)
        )
        if not company:
            raise HTTPException(status_code=404, detail=f"Company with ID {transaction.PaymentTransactionCompanyId} not found")
            
        site = execute_query(
            "SELECT 1 FROM Sites WHERE SiteId = ? AND SiteCompanyID = ?", 
            (transaction.PaymentTransactionSiteId, transaction.PaymentTransactionCompanyId)
        )
        if not site:
            raise HTTPException(status_code=404, detail=f"Site with ID {transaction.PaymentTransactionSiteId} not found")
            
        charger = execute_query(
            "SELECT 1 FROM Chargers WHERE ChargerId = ? AND ChargerCompanyId = ? AND ChargerSiteId = ?", 
            (transaction.PaymentTransactionChargerId, transaction.PaymentTransactionCompanyId, transaction.PaymentTransactionSiteId)
        )
        if not charger:
            raise HTTPException(status_code=404, detail=f"Charger with ID {transaction.PaymentTransactionChargerId} not found")
            
        payment_method = execute_query(
            "SELECT 1 FROM PaymentMethods WHERE PaymentMethodId = ?", 
            (transaction.PaymentTransactionMethodUsed,)
        )
        if not payment_method:
            raise HTTPException(status_code=404, detail=f"Payment method with ID {transaction.PaymentTransactionMethodUsed} not found")
            
        if transaction.PaymentTransactionDriverId:
            driver = execute_query(
                "SELECT 1 FROM Drivers WHERE DriverId = ?", 
                (transaction.PaymentTransactionDriverId,)
            )
            if not driver:
                raise HTTPException(status_code=404, detail=f"Driver with ID {transaction.PaymentTransactionDriverId} not found")
                
        if transaction.PaymentTransactionSessionId:
            session = execute_query(
                "SELECT 1 FROM ChargeSessions WHERE ChargeSessionId = ?", 
                (transaction.PaymentTransactionSessionId,)
            )
            if not session:
                raise HTTPException(status_code=404, detail=f"Session with ID {transaction.PaymentTransactionSessionId} not found")
        
        # Get maximum transaction ID and increment by 1
        max_id_result = execute_query("SELECT MAX(PaymentTransactionId) as max_id FROM PaymentTransactions")
        new_id = 1
        if max_id_result and max_id_result[0]['max_id'] is not None:
            new_id = max_id_result[0]['max_id'] + 1
            
        now = datetime.now().isoformat()
        
        # Insert new payment transaction
        execute_insert(
            """
            INSERT INTO PaymentTransactions (
                PaymentTransactionId, PaymentTransactionMethodUsed, PaymentTransactionDriverId,
                PaymentTransactionDateTime, PaymentTransactionAmount, PaymentTransactionStatus,
                PaymentTransactionPaymentStatus, PaymentTransactionCompanyId, PaymentTransactionSiteId, 
                PaymentTransactionChargerId, PaymentTransactionSessionId, PaymentTransactionStripeIntentId,
                PaymentTransactionCreated, PaymentTransactionUpdated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id,
                transaction.PaymentTransactionMethodUsed,
                transaction.PaymentTransactionDriverId,
                now,
                transaction.PaymentTransactionAmount,
                transaction.PaymentTransactionStatus,
                transaction.PaymentTransactionPaymentStatus if hasattr(transaction, 'PaymentTransactionPaymentStatus') else 'pending',
                transaction.PaymentTransactionCompanyId,
                transaction.PaymentTransactionSiteId,
                transaction.PaymentTransactionChargerId,
                transaction.PaymentTransactionSessionId,
                transaction.PaymentTransactionStripeIntentId,
                now,
                now
            )
        )
        
        # Return the created transaction
        return await get_payment_transaction(new_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating payment transaction: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.put("/{transaction_id}", response_model=PaymentTransaction)
async def update_payment_transaction(transaction_id: int, transaction: PaymentTransactionUpdate):
    """Update an existing payment transaction."""
    try:
        # Check if transaction exists
        existing = execute_query("SELECT 1 FROM PaymentTransactions WHERE PaymentTransactionId = ?", (transaction_id,))
        if not existing:
            raise HTTPException(status_code=404, detail=f"Payment transaction with ID {transaction_id} not found")
        
        # Build update query dynamically based on provided fields
        update_fields = []
        params = []
        
        for field, value in transaction.model_dump(exclude_unset=True).items():
            if value is not None:
                update_fields.append(f"{field} = ?")
                params.append(value)
                
        if not update_fields:
            # No fields to update
            return await get_payment_transaction(transaction_id)
            
        # Add PaymentTransactionUpdated field
        update_fields.append("PaymentTransactionUpdated = ?")
        params.append(datetime.now().isoformat())
        
        # Add transaction_id to params
        params.append(transaction_id)
        
        # Execute update
        execute_update(
            f"UPDATE PaymentTransactions SET {', '.join(update_fields)} WHERE PaymentTransactionId = ?",
            tuple(params)
        )
        
        # Return updated transaction
        return await get_payment_transaction(transaction_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating payment transaction {transaction_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

