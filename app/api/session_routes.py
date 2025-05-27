# app/api/session_routes.py
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging

from app.models.session import ChargeSession
from app.db.database import execute_query
from app.services.session_service import get_session_meter_timeline, calculate_session_energy, track_max_power

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
    offset: int = Query(0, description="Offset for pagination")
):
    """Get a list of charging sessions with optional filtering."""
    try:
        query = "SELECT * FROM ChargeSessions"
        params = []
        
        # Build WHERE clause for filters
        filters = []
        
        if company_id is not None:
            filters.append("ChargerSessionCompanyId = ?")
            params.append(company_id)
            
        if site_id is not None:
            filters.append("ChargerSessionSiteId = ?")
            params.append(site_id)
            
        if charger_id is not None:
            filters.append("ChargerSessionChargerId = ?")
            params.append(charger_id)
            
        if driver_id is not None:
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
    except Exception as e:
        logger.error(f"Error getting sessions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/{session_id}", response_model=ChargeSession)
async def get_session(session_id: int):
    """Get details of a specific charge session by ID."""
    try:
        session = execute_query(
            "SELECT * FROM ChargeSessions WHERE ChargeSessionId = ?", 
            (session_id,)
        )
        
        if not session:
            raise HTTPException(status_code=404, detail=f"Session with ID {session_id} not found")
            
        return session[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/{session_id}/meter_values", response_model=List[Dict[str, Any]])
async def get_session_meter_values(session_id: int):
    """Get meter readings timeline for a specific charge session."""
    try:
        session = execute_query(
            "SELECT 1 FROM ChargeSessions WHERE ChargeSessionId = ?", 
            (session_id,)
        )
        
        if not session:
            raise HTTPException(status_code=404, detail=f"Session with ID {session_id} not found")
            
        meter_values = get_session_meter_timeline(session_id)
        return meter_values
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting meter values for session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/{session_id}/stats", response_model=Dict[str, Any])
async def get_session_stats(session_id: int):
    """Get statistics for a specific charge session."""
    try:
        session = execute_query(
            "SELECT * FROM ChargeSessions WHERE ChargeSessionId = ?", 
            (session_id,)
        )
        
        if not session:
            raise HTTPException(status_code=404, detail=f"Session with ID {session_id} not found")
        
        session_data = session[0]
        
        # Calculate values if not already in database
        energy_kwh = session_data["ChargerSessionEnergyKWH"]
        if energy_kwh is None:
            energy_kwh = calculate_session_energy(session_id)
        
        # Calculate duration if not in database
        duration_seconds = session_data["ChargerSessionDuration"]
        if duration_seconds is None and session_data["ChargerSessionEnd"] is not None:
            start_time = datetime.fromisoformat(session_data["ChargerSessionStart"])
            end_time = datetime.fromisoformat(session_data["ChargerSessionEnd"])
            duration_seconds = int((end_time - start_time).total_seconds())
        
        # Get max power
        max_power_kw = track_max_power(session_id)
        
        # Additional statistics
        avg_power_kw = 0
        if duration_seconds and duration_seconds > 0:
            avg_power_kw = (energy_kwh * 3600) / duration_seconds
        
        return {
            "session_id": session_id,
            "energy_kwh": energy_kwh,
            "duration_seconds": duration_seconds,
            "duration_formatted": str(timedelta(seconds=duration_seconds)) if duration_seconds else None,
            "max_power_kw": max_power_kw,
            "avg_power_kw": avg_power_kw,
            "status": session_data["ChargerSessionStatus"],
            "cost": session_data["ChargerSessionCost"]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting stats for session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/charger/{charger_id}", response_model=List[ChargeSession])
async def get_charger_sessions(
    charger_id: int,
    company_id: int = Query(..., description="Company ID"),
    site_id: int = Query(..., description="Site ID"),
    limit: int = Query(100, description="Limit number of results"),
    offset: int = Query(0, description="Offset for pagination")
):
    """Get all charging sessions for a specific charger."""
    try:
        # Check if charger exists
        charger = execute_query(
            "SELECT 1 FROM Chargers WHERE ChargerId = ? AND ChargerCompanyId = ? AND ChargerSiteId = ?", 
            (charger_id, company_id, site_id)
        )
        
        if not charger:
            raise HTTPException(status_code=404, detail=f"Charger with ID {charger_id} not found")
        
        sessions = execute_query(
            """
            SELECT * FROM ChargeSessions 
            WHERE ChargerSessionChargerId = ? AND ChargerSessionCompanyId = ? AND ChargerSessionSiteId = ?
            ORDER BY ChargerSessionStart DESC
            LIMIT ? OFFSET ?
            """, 
            (charger_id, company_id, site_id, limit, offset)
        )
        
        return sessions
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting sessions for charger {charger_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# Add to site_router to get sessions for a specific site
@router.get("/site/{site_id}", response_model=List[ChargeSession])
async def get_site_sessions(
    site_id: int,
    company_id: int = Query(..., description="Company ID"),
    start_date: Optional[datetime] = Query(None, description="Filter by start date (from)"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date (to)"),
    limit: int = Query(100, description="Limit number of results"),
    offset: int = Query(0, description="Offset for pagination")
):
    """Get all charging sessions for a specific site."""
    try:
        # Check if site exists and belongs to the company
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