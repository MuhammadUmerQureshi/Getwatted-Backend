# app/api/payment_method_routes.py
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional
from datetime import datetime
import logging

from app.models.payment_method import PaymentMethod, PaymentMethodCreate, PaymentMethodUpdate
from app.db.database import execute_query, execute_insert, execute_update, execute_delete

router = APIRouter(prefix="/api/v1/payment_methods", tags=["PAYMENT_METHODS"])


logger = logging.getLogger("ocpp.payment_methods")

@router.get("/", response_model=List[PaymentMethod])
async def get_payment_methods(
    company_id: Optional[int] = Query(None, description="Filter by company ID"),
    enabled: Optional[bool] = Query(None, description="Filter by enabled status")
):
    """Get a list of all payment methods with optional filtering."""
    try:
        query = "SELECT * FROM PaymentMethods"
        params = []
        
        # Build WHERE clause for filters
        filters = []
        
        if company_id is not None:
            filters.append("PaymentMethodCompanyId = ?")
            params.append(company_id)
            
        if enabled is not None:
            filters.append("PaymentMethodEnabled = ?")
            params.append(1 if enabled else 0)
            
        if filters:
            query += f" WHERE {' AND '.join(filters)}"
            
        query += " ORDER BY PaymentMethodName"
        
        payment_methods = execute_query(query, tuple(params) if params else None)
        return payment_methods
    except Exception as e:
        logger.error(f"Error getting payment methods: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/{payment_method_id}", response_model=PaymentMethod)
async def get_payment_method(payment_method_id: int):
    """Get details of a specific payment method by ID."""
    try:
        payment_method = execute_query(
            "SELECT * FROM PaymentMethods WHERE PaymentMethodId = ?", 
            (payment_method_id,)
        )
        
        if not payment_method:
            raise HTTPException(status_code=404, detail=f"Payment method with ID {payment_method_id} not found")
            
        return payment_method[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting payment method {payment_method_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.post("/", response_model=PaymentMethod, status_code=201)
async def create_payment_method(payment_method: PaymentMethodCreate):
    """Create a new payment method."""
    try:
        # Check if company exists
        company = execute_query(
            "SELECT 1 FROM Companies WHERE CompanyId = ?", 
            (payment_method.PaymentMethodCompanyId,)
        )
        
        if not company:
            raise HTTPException(status_code=404, detail=f"Company with ID {payment_method.PaymentMethodCompanyId} not found")
        
        # Get maximum payment method ID and increment by 1
        max_id_result = execute_query("SELECT MAX(PaymentMethodId) as max_id FROM PaymentMethods")
        new_id = 1
        if max_id_result and max_id_result[0]['max_id'] is not None:
            new_id = max_id_result[0]['max_id'] + 1
            
        now = datetime.now().isoformat()
        
        # Insert new payment method
        execute_insert(
            """
            INSERT INTO PaymentMethods (
                PaymentMethodId, PaymentMethodCompanyId, PaymentMethodName, 
                PaymentMethodEnabled, PaymentMethodCreated, PaymentMethodUpdated
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                new_id,
                payment_method.PaymentMethodCompanyId,
                payment_method.PaymentMethodName,
                1 if payment_method.PaymentMethodEnabled else 0,
                now,
                now
            )
        )
        
        # Return the created payment method
        return await get_payment_method(new_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating payment method: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.put("/{payment_method_id}", response_model=PaymentMethod)
async def update_payment_method(payment_method_id: int, payment_method: PaymentMethodUpdate):
    """Update an existing payment method."""
    try:
        # Check if payment method exists
        existing = execute_query("SELECT 1 FROM PaymentMethods WHERE PaymentMethodId = ?", (payment_method_id,))
        if not existing:
            raise HTTPException(status_code=404, detail=f"Payment method with ID {payment_method_id} not found")
        
        # Build update query dynamically based on provided fields
        update_fields = []
        params = []
        
        for field, value in payment_method.model_dump(exclude_unset=True).items():
            if value is not None:
                # Convert boolean to integer for SQLite
                if isinstance(value, bool):
                    value = 1 if value else 0
                update_fields.append(f"{field} = ?")
                params.append(value)
                
        if not update_fields:
            # No fields to update
            return await get_payment_method(payment_method_id)
            
        # Add PaymentMethodUpdated field
        update_fields.append("PaymentMethodUpdated = ?")
        params.append(datetime.now().isoformat())
        
        # Add payment_method_id to params
        params.append(payment_method_id)
        
        # Execute update
        execute_update(
            f"UPDATE PaymentMethods SET {', '.join(update_fields)} WHERE PaymentMethodId = ?",
            tuple(params)
        )
        
        # Return updated payment method
        return await get_payment_method(payment_method_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating payment method {payment_method_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.delete("/{payment_method_id}", status_code=204)
async def delete_payment_method(payment_method_id: int):
    """Delete a payment method."""
    try:
        # Check if payment method exists
        existing = execute_query("SELECT 1 FROM PaymentMethods WHERE PaymentMethodId = ?", (payment_method_id,))
        if not existing:
            raise HTTPException(status_code=404, detail=f"Payment method with ID {payment_method_id} not found")
        
        # Check if payment method is being used by any transactions
        transactions_using_method = execute_query(
            "SELECT 1 FROM PaymentTransactions WHERE PaymentTransactionMethodUsed = ?", 
            (payment_method_id,)
        )
        
        if transactions_using_method:
            raise HTTPException(
                status_code=400, 
                detail=f"Cannot delete payment method {payment_method_id} because it is associated with one or more payment transactions"
            )
            
        # Delete payment method
        rows_deleted = execute_delete("DELETE FROM PaymentMethods WHERE PaymentMethodId = ?", (payment_method_id,))
        
        if rows_deleted == 0:
            raise HTTPException(status_code=500, detail=f"Failed to delete payment method {payment_method_id}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting payment method {payment_method_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")