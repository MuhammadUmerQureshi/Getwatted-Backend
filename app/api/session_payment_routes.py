# app/api/session_payment_routes.py
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
import logging

from app.services.session_payment_service import SessionPaymentService

router = APIRouter(prefix="/api/v1/session_payments", tags=["session_payments"])

logger = logging.getLogger("ocpp.session_payments")

@router.get("/{session_id}/status")
async def get_session_payment_status(session_id: int):
    """Get comprehensive payment status for a charge session."""
    try:
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
async def mark_session_as_paid(session_id: int, payment_transaction_id: int):
    """Mark a session as fully paid."""
    try:
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
    limit: int = Query(100, description="Limit number of results")
):
    """Get sessions that require payment but haven't been paid."""
    try:
        unpaid_sessions = await SessionPaymentService.get_unpaid_sessions(
            company_id=company_id,
            site_id=site_id,
            charger_id=charger_id,
            limit=limit
        )
        
        return {"unpaid_sessions": unpaid_sessions, "count": len(unpaid_sessions)}
    except Exception as e:
        logger.error(f"Error getting unpaid sessions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.put("/transaction/{transaction_id}/status")
async def update_payment_transaction_status(
    transaction_id: int,
    payment_status: str = Query(..., description="New payment status (pending, completed, failed, canceled, refunded)")
):
    """Update payment transaction status and sync with charge session."""
    try:
        # Validate payment status
        valid_statuses = ["pending", "completed", "failed", "canceled", "refunded"]
        if payment_status not in valid_statuses:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid payment status. Must be one of: {', '.join(valid_statuses)}"
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
    site_id: Optional[int] = Query(None, description="Filter by site ID")
):
    """Get payment statistics across sessions."""
    try:
        from app.db.database import execute_query
        
        # Build query based on filters
        base_query = """
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
            base_query += f" WHERE {' AND '.join(filters)}"
        
        stats = execute_query(base_query, tuple(params) if params else None)
        
        if stats:
            result = stats[0]
            # Calculate percentages
            total_requiring_payment = result["sessions_requiring_payment"] or 1  # Avoid division by zero
            
            return {
                "total_sessions": result["total_sessions"],
                "sessions_requiring_payment": result["sessions_requiring_payment"],
                "paid_sessions": result["paid_sessions"],
                "pending_payments": result["pending_payments"],
                "failed_payments": result["failed_payments"],
                "total_revenue": float(result["total_revenue"] or 0),
                "pending_revenue": float(result["pending_revenue"] or 0),
                "payment_success_rate": round((result["paid_sessions"] / total_requiring_payment) * 100, 2),
                "company_id": company_id,
                "site_id": site_id
            }
        else:
            return {"error": "No data found"}
            
    except Exception as e:
        logger.error(f"Error getting payment statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")