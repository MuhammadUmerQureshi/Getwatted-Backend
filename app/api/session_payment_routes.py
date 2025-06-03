# app/api/session_payment_routes.py
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional
import logging

from app.services.session_payment_service import SessionPaymentService
from app.models.auth import UserInToken
from app.dependencies.auth import (
    require_role,
    get_current_user,
    require_company_access,
    require_admin_or_higher
)
from app.db.database import execute_query

router = APIRouter(prefix="/api/v1/session_payments", tags=["SESSION_PAYMENTS"])

logger = logging.getLogger("ocpp.session_payments")

@router.get("/{session_id}/status")
async def get_session_payment_status(
    session_id: int,
    user: UserInToken = Depends(get_current_user)
):
    """
    Get comprehensive payment status for a charge session.
    
    - SuperAdmin: Can view payment status for any session
    - Admin: Can only view payment status for sessions in their company
    - Driver: Can only view payment status for their own sessions
    """
    try:
        # Verify session access
        session = execute_query(
            """
            SELECT ChargerSessionDriverId, ChargerSessionCompanyId 
            FROM ChargeSessions 
            WHERE ChargeSessionId = ?
            """,
            (session_id,)
        )
        
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Session {session_id} not found"
            )
            
        # Check access based on role
        if user.role.value == "Driver":
            if session[0]["ChargerSessionDriverId"] != user.driver_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only view payment status for your own sessions"
                )
        elif user.role.value == "Admin":
            if session[0]["ChargerSessionCompanyId"] != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only view payment status for sessions in your company"
                )
        
        status = await SessionPaymentService.get_session_payment_status(session_id)
        
        if "error" in status:
            raise HTTPException(status_code=404, detail=status["error"])
            
        return status
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session payment status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.post("/{session_id}/mark_paid")
async def mark_session_as_paid(
    session_id: int,
    payment_transaction_id: int,
    user: UserInToken = Depends(require_admin_or_higher)
):
    """
    Mark a session as fully paid.
    
    - SuperAdmin: Can mark any session as paid
    - Admin: Can only mark sessions from their company as paid
    - Driver: Not allowed to access this endpoint
    """
    try:
        # Verify session access
        session = execute_query(
            """
            SELECT ChargerSessionCompanyId 
            FROM ChargeSessions 
            WHERE ChargeSessionId = ?
            """,
            (session_id,)
        )
        
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Session {session_id} not found"
            )
            
        # Check company access
        if user.role.value == "Admin":
            if session[0]["ChargerSessionCompanyId"] != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only mark sessions from your company as paid"
                )
        
        # Verify payment transaction belongs to the same company
        transaction = execute_query(
            """
            SELECT PaymentTransactionCompanyId 
            FROM PaymentTransactions 
            WHERE PaymentTransactionId = ?
            """,
            (payment_transaction_id,)
        )
        
        if not transaction:
            raise HTTPException(
                status_code=404,
                detail=f"Payment transaction {payment_transaction_id} not found"
            )
            
        if user.role.value == "Admin":
            if transaction[0]["PaymentTransactionCompanyId"] != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="Payment transaction must belong to your company"
                )
        
        success = await SessionPaymentService.mark_session_as_paid(session_id, payment_transaction_id)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to mark session as paid")
            
        return {"status": "success", "message": f"Session {session_id} marked as paid"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking session as paid: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/unpaid")
async def get_unpaid_sessions(
    company_id: Optional[int] = Query(None, description="Filter by company ID"),
    site_id: Optional[int] = Query(None, description="Filter by site ID"),
    charger_id: Optional[int] = Query(None, description="Filter by charger ID"),
    limit: int = Query(100, description="Limit number of results"),
    user: UserInToken = Depends(get_current_user)
):
    """
    Get sessions that require payment but haven't been paid.
    
    - SuperAdmin: Can view unpaid sessions for any company
    - Admin: Can only view unpaid sessions for their company
    - Driver: Can only view their own unpaid sessions
    """
    try:
        # Apply role-based filtering
        if user.role.value == "Driver":
            # Drivers can only see their own unpaid sessions
            unpaid_sessions = await SessionPaymentService.get_unpaid_sessions(
                company_id=user.company_id,
                site_id=site_id,
                charger_id=charger_id,
                driver_id=user.driver_id,
                limit=limit
            )
        elif user.role.value == "Admin":
            # Admins can only see unpaid sessions for their company
            if company_id and company_id != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only view unpaid sessions for your company"
                )
            unpaid_sessions = await SessionPaymentService.get_unpaid_sessions(
                company_id=user.company_id,
                site_id=site_id,
                charger_id=charger_id,
                limit=limit
            )
        else:  # SuperAdmin
            unpaid_sessions = await SessionPaymentService.get_unpaid_sessions(
                company_id=company_id,
                site_id=site_id,
                charger_id=charger_id,
                limit=limit
            )
        
        return {"unpaid_sessions": unpaid_sessions, "count": len(unpaid_sessions)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting unpaid sessions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.put("/transaction/{transaction_id}/status")
async def update_payment_transaction_status(
    transaction_id: int,
    payment_status: str = Query(..., description="New payment status (pending, completed, failed, canceled, refunded)"),
    user: UserInToken = Depends(require_admin_or_higher)
):
    """
    Update payment transaction status and sync with charge session.
    
    - SuperAdmin: Can update any payment transaction status
    - Admin: Can only update payment transaction status for their company
    - Driver: Not allowed to access this endpoint
    """
    try:
        # Validate payment status
        valid_statuses = ["pending", "completed", "failed", "canceled", "refunded"]
        if payment_status not in valid_statuses:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid payment status. Must be one of: {', '.join(valid_statuses)}"
            )
        
        # Verify transaction access
        transaction = execute_query(
            """
            SELECT PaymentTransactionCompanyId 
            FROM PaymentTransactions 
            WHERE PaymentTransactionId = ?
            """,
            (transaction_id,)
        )
        
        if not transaction:
            raise HTTPException(
                status_code=404,
                detail=f"Payment transaction {transaction_id} not found"
            )
            
        # Check company access
        if user.role.value == "Admin":
            if transaction[0]["PaymentTransactionCompanyId"] != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only update payment transaction status for your company"
                )
        
        success = await SessionPaymentService.update_payment_transaction_status(
            transaction_id=transaction_id,
            payment_status=payment_status
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update payment status")
            
        return {
            "status": "success", 
            "message": f"Payment transaction {transaction_id} status updated to {payment_status}"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating payment transaction status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/statistics")
async def get_payment_statistics(
    company_id: Optional[int] = Query(None, description="Filter by company ID"),
    site_id: Optional[int] = Query(None, description="Filter by site ID"),
    user: UserInToken = Depends(get_current_user)
):
    """
    Get payment statistics across sessions.
    
    - SuperAdmin: Can view statistics for any company
    - Admin: Can only view statistics for their company
    - Driver: Can only view statistics for their own sessions
    """
    try:
        # Apply role-based filtering
        if user.role.value == "Driver":
            # Drivers can only see their own statistics
            stats = execute_query(
                """
                SELECT 
                    COUNT(*) as total_sessions,
                    COUNT(CASE WHEN ChargerSessionCost > 0 THEN 1 END) as sessions_requiring_payment,
                    COUNT(CASE WHEN ChargerSessionPaymentStatus = 'completed' THEN 1 END) as paid_sessions,
                    COUNT(CASE WHEN ChargerSessionPaymentStatus = 'pending' THEN 1 END) as pending_payments,
                    COUNT(CASE WHEN ChargerSessionPaymentStatus = 'failed' THEN 1 END) as failed_payments,
                    SUM(CASE WHEN ChargerSessionPaymentStatus = 'completed' THEN ChargerSessionCost ELSE 0 END) as total_revenue,
                    SUM(CASE WHEN ChargerSessionPaymentStatus != 'completed' AND ChargerSessionCost > 0 THEN ChargerSessionCost ELSE 0 END) as pending_revenue
                FROM ChargeSessions
                WHERE ChargerSessionCompanyId = ? AND ChargerSessionDriverId = ?
                """,
                (user.company_id, user.driver_id)
            )
        elif user.role.value == "Admin":
            # Admins can only see statistics for their company
            if company_id and company_id != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only view statistics for your company"
                )
            
            query = """
                SELECT 
                    COUNT(*) as total_sessions,
                    COUNT(CASE WHEN ChargerSessionCost > 0 THEN 1 END) as sessions_requiring_payment,
                    COUNT(CASE WHEN ChargerSessionPaymentStatus = 'completed' THEN 1 END) as paid_sessions,
                    COUNT(CASE WHEN ChargerSessionPaymentStatus = 'pending' THEN 1 END) as pending_payments,
                    COUNT(CASE WHEN ChargerSessionPaymentStatus = 'failed' THEN 1 END) as failed_payments,
                    SUM(CASE WHEN ChargerSessionPaymentStatus = 'completed' THEN ChargerSessionCost ELSE 0 END) as total_revenue,
                    SUM(CASE WHEN ChargerSessionPaymentStatus != 'completed' AND ChargerSessionCost > 0 THEN ChargerSessionCost ELSE 0 END) as pending_revenue
                FROM ChargeSessions
                WHERE ChargerSessionCompanyId = ?
            """
            params = [user.company_id]
            
            if site_id is not None:
                query += " AND ChargerSessionSiteId = ?"
                params.append(site_id)
                
            stats = execute_query(query, tuple(params))
        else:  # SuperAdmin
            # Build query based on filters
            query = """
                SELECT 
                    COUNT(*) as total_sessions,
                    COUNT(CASE WHEN ChargerSessionCost > 0 THEN 1 END) as sessions_requiring_payment,
                    COUNT(CASE WHEN ChargerSessionPaymentStatus = 'completed' THEN 1 END) as paid_sessions,
                    COUNT(CASE WHEN ChargerSessionPaymentStatus = 'pending' THEN 1 END) as pending_payments,
                    COUNT(CASE WHEN ChargerSessionPaymentStatus = 'failed' THEN 1 END) as failed_payments,
                    SUM(CASE WHEN ChargerSessionPaymentStatus = 'completed' THEN ChargerSessionCost ELSE 0 END) as total_revenue,
                    SUM(CASE WHEN ChargerSessionPaymentStatus != 'completed' AND ChargerSessionCost > 0 THEN ChargerSessionCost ELSE 0 END) as pending_revenue
                FROM ChargeSessions
            """
            params = []
            filters = []
            
            if company_id is not None:
                filters.append("ChargerSessionCompanyId = ?")
                params.append(company_id)
                
            if site_id is not None:
                filters.append("ChargerSessionSiteId = ?")
                params.append(site_id)
                
            if filters:
                query += f" WHERE {' AND '.join(filters)}"
                
            stats = execute_query(query, tuple(params) if params else None)
        
        return stats[0] if stats else {
            "total_sessions": 0,
            "sessions_requiring_payment": 0,
            "paid_sessions": 0,
            "pending_payments": 0,
            "failed_payments": 0,
            "total_revenue": 0,
            "pending_revenue": 0
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting payment statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")