# app/api/payment_transaction_routes.py
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional
from datetime import datetime
import logging

from app.models.payment_method import PaymentTransaction, PaymentTransactionCreate, PaymentTransactionUpdate
from app.models.auth import UserInToken
from app.db.database import execute_query, execute_insert, execute_update, execute_delete
from app.dependencies.auth import (
    require_role,
    get_current_user,
    require_admin_or_higher,
    check_company_access
)

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
    offset: int = Query(0, description="Offset for pagination"),
    user: UserInToken = Depends(get_current_user)
):
    """
    Get a list of payment transactions with optional filtering.
    
    - SuperAdmin: Can see all transactions
    - Admin: Can only see transactions from their company
    - Driver: Can only see their own transactions
    """
    try:
        query = "SELECT * FROM PaymentTransactions"
        params = []
        filters = []
        
        # Apply role-based filtering
        if user.role.value == "Driver":
            filters.append("PaymentTransactionDriverId = ?")
            params.append(user.driver_id)
        elif user.role.value == "Admin":
            company_id = user.company_id
        
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
            # Only allow filtering by driver_id if user is SuperAdmin or Admin
            if user.role.value == "Driver":
                raise HTTPException(
                    status_code=403,
                    detail="You cannot filter by driver ID"
                )
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
        params.extend([limit, offset])
        
        transactions = execute_query(query, tuple(params))
        return transactions
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting payment transactions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/stripe/{stripe_intent_id}", response_model=PaymentTransaction)
async def get_transaction_by_stripe_intent(
    stripe_intent_id: str,
    user: UserInToken = Depends(get_current_user)
):
    """
    Get payment transaction by Stripe payment intent ID.
    
    - SuperAdmin: Can see any transaction
    - Admin: Can only see transactions from their company
    - Driver: Can only see their own transactions
    """
    try:
        transaction = execute_query(
            "SELECT * FROM PaymentTransactions WHERE PaymentTransactionStripeIntentId = ?", 
            (stripe_intent_id,)
        )
        
        if not transaction:
            raise HTTPException(status_code=404, detail=f"Payment transaction with Stripe intent ID {stripe_intent_id} not found")
            
        # Check access based on role
        if user.role.value == "Driver":
            if transaction[0]["PaymentTransactionDriverId"] != user.driver_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only view your own transactions"
                )
        elif user.role.value == "Admin":
            if transaction[0]["PaymentTransactionCompanyId"] != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only view transactions from your company"
                )
            
        return transaction[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting payment transaction by Stripe intent {stripe_intent_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/{transaction_id}", response_model=PaymentTransaction)
async def get_payment_transaction(
    transaction_id: int,
    user: UserInToken = Depends(get_current_user)
):
    """
    Get details of a specific payment transaction by ID.
    
    - SuperAdmin: Can see any transaction
    - Admin: Can only see transactions from their company
    - Driver: Can only see their own transactions
    """
    try:
        transaction = execute_query(
            "SELECT * FROM PaymentTransactions WHERE PaymentTransactionId = ?", 
            (transaction_id,)
        )
        
        if not transaction:
            raise HTTPException(status_code=404, detail=f"Payment transaction with ID {transaction_id} not found")
            
        # Check access based on role
        if user.role.value == "Driver":
            if transaction[0]["PaymentTransactionDriverId"] != user.driver_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only view your own transactions"
                )
        elif user.role.value == "Admin":
            if transaction[0]["PaymentTransactionCompanyId"] != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only view transactions from your company"
                )
            
        return transaction[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting payment transaction {transaction_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.post("/", response_model=PaymentTransaction, status_code=201)
async def create_payment_transaction(
    transaction: PaymentTransactionCreate,
    user: UserInToken = Depends(require_admin_or_higher)
):
    """
    Create a new payment transaction.
    
    - SuperAdmin: Can create transactions for any company
    - Admin: Can only create transactions for their company
    - Driver: Not allowed to access this endpoint
    """
    try:
        # Check company access
        if user.role.value != "SuperAdmin":
            if transaction.PaymentTransactionCompanyId != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only create transactions for your company"
                )
        
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
            "SELECT 1 FROM PaymentMethods WHERE PaymentMethodId = ? AND PaymentMethodCompanyId = ?", 
            (transaction.PaymentTransactionMethodUsed, transaction.PaymentTransactionCompanyId)
        )
        if not payment_method:
            raise HTTPException(status_code=404, detail=f"Payment method with ID {transaction.PaymentTransactionMethodUsed} not found")
            
        if transaction.PaymentTransactionDriverId:
            driver = execute_query(
                "SELECT 1 FROM Drivers WHERE DriverId = ? AND DriverCompanyId = ?", 
                (transaction.PaymentTransactionDriverId, transaction.PaymentTransactionCompanyId)
            )
            if not driver:
                raise HTTPException(status_code=404, detail=f"Driver with ID {transaction.PaymentTransactionDriverId} not found")
                
        if transaction.PaymentTransactionSessionId:
            session = execute_query(
                "SELECT 1 FROM ChargeSessions WHERE ChargeSessionId = ? AND ChargerSessionCompanyId = ?", 
                (transaction.PaymentTransactionSessionId, transaction.PaymentTransactionCompanyId)
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
async def update_payment_transaction(
    transaction_id: int,
    transaction: PaymentTransactionUpdate,
    user: UserInToken = Depends(require_admin_or_higher)
):
    """
    Update an existing payment transaction.
    
    - SuperAdmin: Can update any transaction
    - Admin: Can only update transactions from their company
    - Driver: Not allowed to access this endpoint
    """
    try:
        # Check if transaction exists and get current data
        existing = execute_query(
            "SELECT * FROM PaymentTransactions WHERE PaymentTransactionId = ?", 
            (transaction_id,)
        )
        if not existing:
            raise HTTPException(status_code=404, detail=f"Payment transaction with ID {transaction_id} not found")
            
        # Check company access
        if user.role.value != "SuperAdmin":
            if existing[0]["PaymentTransactionCompanyId"] != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only update transactions from your company"
                )
            # Prevent changing company
            if transaction.PaymentTransactionCompanyId is not None and transaction.PaymentTransactionCompanyId != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You cannot change the company of a transaction"
                )
        
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

# Company-specific endpoints

@router.get("/company/{company_id}", response_model=List[PaymentTransaction])
async def get_company_payment_transactions(
    company_id: int,
    start_date: Optional[datetime] = Query(None, description="Filter by start date (from)"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date (to)"),
    status: Optional[str] = Query(None, description="Filter by transaction status"),
    limit: int = Query(100, description="Limit number of results"),
    offset: int = Query(0, description="Offset for pagination"),
    user: UserInToken = Depends(require_admin_or_higher)
):
    """
    Get all payment transactions for a specific company.
    
    - SuperAdmin: Can see transactions from any company
    - Admin: Can only see transactions from their company
    - Driver: Not allowed to access this endpoint
    """
    try:
        # Check company access
        check_company_access(user, company_id)

        query = "SELECT * FROM PaymentTransactions WHERE PaymentTransactionCompanyId = ?"
        params = [company_id]
        
        if start_date:
            query += " AND PaymentTransactionCreated >= ?"
            params.append(start_date.isoformat())
            
        if end_date:
            query += " AND PaymentTransactionCreated <= ?"
            params.append(end_date.isoformat())
            
        if status:
            query += " AND PaymentTransactionStatus = ?"
            params.append(status)
            
        query += " ORDER BY PaymentTransactionCreated DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        transactions = execute_query(query, tuple(params))
        return transactions
        
    except Exception as e:
        logger.error(f"Error getting payment transactions for company {company_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# Driver-specific endpoints

@router.get("/driver/{driver_id}", response_model=List[PaymentTransaction])
async def get_driver_transactions(
    driver_id: int,
    company_id: Optional[int] = Query(None, description="Filter by company ID"),
    site_id: Optional[int] = Query(None, description="Filter by site ID"),
    charger_id: Optional[int] = Query(None, description="Filter by charger ID"),
    payment_method_id: Optional[int] = Query(None, description="Filter by payment method ID"),
    status: Optional[str] = Query(None, description="Filter by transaction status"),
    start_date: Optional[datetime] = Query(None, description="Filter by start date (from)"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date (to)"),
    limit: int = Query(100, description="Limit number of results"),
    offset: int = Query(0, description="Offset for pagination"),
    user: UserInToken = Depends(get_current_user)
):
    """
    Get all payment transactions for a specific driver.
    
    - SuperAdmin: Can see transactions for any driver
    - Admin: Can only see transactions for drivers in their company
    - Driver: Can only see their own transactions
    """
    try:
        # Check access based on role
        if user.role.value == "Driver":
            if driver_id != user.driver_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only view your own transactions"
                )
        elif user.role.value == "Admin":
            # Verify driver belongs to admin's company
            driver = execute_query(
                "SELECT 1 FROM Drivers WHERE DriverId = ? AND DriverCompanyId = ?",
                (driver_id, user.company_id)
            )
            if not driver:
                raise HTTPException(
                    status_code=403,
                    detail="You can only view transactions for drivers in your company"
                )
            company_id = user.company_id
        
        query = "SELECT * FROM PaymentTransactions WHERE PaymentTransactionDriverId = ?"
        params = [driver_id]
        
        if company_id is not None:
            query += " AND PaymentTransactionCompanyId = ?"
            params.append(company_id)
            
        if site_id is not None:
            query += " AND PaymentTransactionSiteId = ?"
            params.append(site_id)
            
        if charger_id is not None:
            query += " AND PaymentTransactionChargerId = ?"
            params.append(charger_id)
            
        if payment_method_id is not None:
            query += " AND PaymentTransactionMethodUsed = ?"
            params.append(payment_method_id)
            
        if status is not None:
            query += " AND PaymentTransactionStatus = ?"
            params.append(status)
            
        if start_date is not None:
            query += " AND PaymentTransactionDateTime >= ?"
            params.append(start_date.isoformat())
            
        if end_date is not None:
            query += " AND PaymentTransactionDateTime <= ?"
            params.append(end_date.isoformat())
            
        query += " ORDER BY PaymentTransactionDateTime DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        transactions = execute_query(query, tuple(params))
        return transactions
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting transactions for driver {driver_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

