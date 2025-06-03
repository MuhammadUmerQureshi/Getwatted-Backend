# app/api/session_routes.py
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging

from app.models.session import ChargeSession, ChargeSessionCreate, ChargeSessionUpdate
from app.models.auth import UserInToken
from app.db.database import execute_query, execute_insert, execute_update, execute_delete
from app.services.session_service import get_session_meter_timeline, calculate_session_energy, track_max_power
from app.dependencies.auth import (
    require_role,
    get_current_user,
    require_admin_or_higher,
    check_company_access
)

router = APIRouter(prefix="/api/v1/sessions", tags=["SESSIONS"])

logger = logging.getLogger("ocpp.sessions")

@router.get("/", response_model=List[ChargeSession])
async def get_sessions(
    company_id: Optional[int] = Query(None, description="Filter by company ID"),
    site_id: Optional[int] = Query(None, description="Filter by site ID"),
    charger_id: Optional[int] = Query(None, description="Filter by charger ID"),
    driver_id: Optional[int] = Query(None, description="Filter by driver ID"),
    rfid_card: Optional[str] = Query(None, description="Filter by RFID card"),
    status: Optional[str] = Query(None, description="Filter by session status"),
    start_date: Optional[datetime] = Query(None, description="Filter by start date (from)"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date (to)"),
    limit: int = Query(100, description="Limit number of results"),
    offset: int = Query(0, description="Offset for pagination"),
    user: UserInToken = Depends(get_current_user)
):
    """
    Get a list of charging sessions with optional filtering.
    
    - SuperAdmin: Can see all sessions
    - Admin: Can only see sessions from their company
    - Driver: Can only see their own sessions
    """
    try:
        query = "SELECT * FROM ChargeSessions"
        params = []
        filters = []
        
        # Apply role-based filtering
        if user.role.value == "Driver":
            filters.append("ChargerSessionDriverId = ?")
            params.append(user.driver_id)
        elif user.role.value == "Admin":
            filters.append("ChargerSessionCompanyId = ?")
            params.append(user.company_id)
        
        # Apply additional filters
        if company_id is not None:
            if user.role.value == "SuperAdmin":
                filters.append("ChargerSessionCompanyId = ?")
                params.append(company_id)
            elif user.role.value == "Admin" and company_id != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only view sessions from your company"
                )
            
        if site_id is not None:
            filters.append("ChargerSessionSiteId = ?")
            params.append(site_id)
            
        if charger_id is not None:
            filters.append("ChargerSessionChargerId = ?")
            params.append(charger_id)
            
        if driver_id is not None:
            if user.role.value == "Driver" and driver_id != user.driver_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only view your own sessions"
                )
            filters.append("ChargerSessionDriverId = ?")
            params.append(driver_id)
            
        if rfid_card is not None:
            filters.append("ChargerSessionRFIDCard = ?")
            params.append(rfid_card)
            
        if status is not None:
            filters.append("ChargerSessionStatus = ?")
            params.append(status)
            
        if start_date is not None:
            filters.append("ChargerSessionStart >= ?")
            params.append(start_date.isoformat())
            
        if end_date is not None:
            filters.append("ChargerSessionStart <= ?")
            params.append(end_date.isoformat())
            
        if filters:
            query += f" WHERE {' AND '.join(filters)}"
            
        query += " ORDER BY ChargerSessionStart DESC LIMIT ? OFFSET ?"
        params.append(limit)
        params.append(offset)
        
        sessions = execute_query(query, tuple(params))
        return sessions
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting sessions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/{session_id}", response_model=ChargeSession)
async def get_session(
    session_id: int,
    user: UserInToken = Depends(get_current_user)
):
    """
    Get a specific charging session by ID.
    
    - SuperAdmin: Can see any session
    - Admin: Can only see sessions from their company
    - Driver: Can only see their own sessions
    """
    try:
        # Get session
        session = execute_query(
            "SELECT * FROM ChargeSessions WHERE ChargerSessionId = ?",
            (session_id,)
        )
        
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Session with ID {session_id} not found"
            )
            
        # Check access permissions
        if user.role.value == "Driver":
            if session[0]["ChargerSessionDriverId"] != user.driver_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only view your own sessions"
                )
        elif user.role.value == "Admin":
            if session[0]["ChargerSessionCompanyId"] != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only view sessions from your company"
                )
        
        return session[0]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/{session_id}/meter-timeline")
async def get_session_meter_values(
    session_id: int,
    user: UserInToken = Depends(get_current_user)
):
    """
    Get meter value timeline for a specific session.
    
    - SuperAdmin: Can see any session's meter values
    - Admin: Can only see meter values from their company's sessions
    - Driver: Can only see their own session's meter values
    """
    try:
        # Get session first to check permissions
        session = execute_query(
            "SELECT * FROM ChargeSessions WHERE ChargerSessionId = ?",
            (session_id,)
        )
        
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Session with ID {session_id} not found"
            )
            
        # Check access permissions
        if user.role.value == "Driver":
            if session[0]["ChargerSessionDriverId"] != user.driver_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only view your own sessions"
                )
        elif user.role.value == "Admin":
            if session[0]["ChargerSessionCompanyId"] != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only view sessions from your company"
                )
        
        # Get meter timeline
        timeline = get_session_meter_timeline(session_id)
        return timeline
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting meter timeline for session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/{session_id}/energy")
async def get_session_energy(
    session_id: int,
    user: UserInToken = Depends(get_current_user)
):
    """
    Get energy consumption data for a specific session.
    
    - SuperAdmin: Can see any session's energy data
    - Admin: Can only see energy data from their company's sessions
    - Driver: Can only see their own session's energy data
    """
    try:
        # Get session first to check permissions
        session = execute_query(
            "SELECT * FROM ChargeSessions WHERE ChargerSessionId = ?",
            (session_id,)
        )
        
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Session with ID {session_id} not found"
            )
            
        # Check access permissions
        if user.role.value == "Driver":
            if session[0]["ChargerSessionDriverId"] != user.driver_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only view your own sessions"
                )
        elif user.role.value == "Admin":
            if session[0]["ChargerSessionCompanyId"] != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only view sessions from your company"
                )
        
        # Calculate energy data
        energy_data = calculate_session_energy(session_id)
        return energy_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting energy data for session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/{session_id}/max-power")
async def get_session_max_power(
    session_id: int,
    user: UserInToken = Depends(get_current_user)
):
    """
    Get maximum power data for a specific session.
    
    - SuperAdmin: Can see any session's power data
    - Admin: Can only see power data from their company's sessions
    - Driver: Can only see their own session's power data
    """
    try:
        # Get session first to check permissions
        session = execute_query(
            "SELECT * FROM ChargeSessions WHERE ChargerSessionId = ?",
            (session_id,)
        )
        
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Session with ID {session_id} not found"
            )
            
        # Check access permissions
        if user.role.value == "Driver":
            if session[0]["ChargerSessionDriverId"] != user.driver_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only view your own sessions"
                )
        elif user.role.value == "Admin":
            if session[0]["ChargerSessionCompanyId"] != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only view sessions from your company"
                )
        
        # Get max power data
        power_data = track_max_power(session_id)
        return power_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting max power data for session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# Site-specific session endpoints
@router.get("/site/{site_id}", response_model=List[ChargeSession])
async def get_site_sessions(
    site_id: int,
    company_id: int = Query(..., description="Company ID"),
    start_date: Optional[datetime] = Query(None, description="Filter by start date (from)"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date (to)"),
    limit: int = Query(100, description="Limit number of results"),
    offset: int = Query(0, description="Offset for pagination"),
    user: UserInToken = Depends(get_current_user)
):
    """
    Get all charging sessions for a specific site.
    
    - SuperAdmin: Can see sessions from any company
    - Admin: Can only see sessions from their company
    - Driver: Can only see their own sessions
    """
    try:
        # Check company access
        check_company_access(user, company_id)

        # Check if site exists and belongs to company
        site = execute_query(
            "SELECT 1 FROM Sites WHERE SiteId = ? AND SiteCompanyID = ?",
            (site_id, company_id)
        )
        if not site:
            raise HTTPException(
                status_code=404,
                detail=f"Site with ID {site_id} not found or does not belong to company {company_id}"
            )
        
        query = """
            SELECT * FROM ChargeSessions 
            WHERE ChargerSessionSiteId = ? AND ChargerSessionCompanyId = ?
        """
        params = [site_id, company_id]
        
        # Apply role-based filtering for drivers
        if user.role.value == "Driver":
            query += " AND ChargerSessionDriverId = ?"
            params.append(user.driver_id)
        
        if start_date:
            query += " AND ChargerSessionStart >= ?"
            params.append(start_date.isoformat())
            
        if end_date:
            query += " AND ChargerSessionStart <= ?"
            params.append(end_date.isoformat())
            
        query += " ORDER BY ChargerSessionStart DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        sessions = execute_query(query, tuple(params))
        return sessions
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting sessions for site {site_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")