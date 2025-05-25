# app/api/event_routes.py
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging

from app.models.event import EventData, EventSummary, EventTypeStats
from app.db.database import execute_query

router = APIRouter(prefix="/api/v1/events", tags=["events"])
company_router = APIRouter(prefix="/api/v1/companies", tags=["companies"])
site_router = APIRouter(prefix="/api/v1/sites", tags=["sites"])
charger_router = APIRouter(prefix="/api/v1/chargers", tags=["chargers"])
session_router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])

logger = logging.getLogger("ocpp.events")

@router.get("/", response_model=List[EventData])
async def get_events(
    company_id: Optional[int] = Query(None, description="Filter by company ID"),
    site_id: Optional[int] = Query(None, description="Filter by site ID"),
    charger_id: Optional[int] = Query(None, description="Filter by charger ID"),
    connector_id: Optional[int] = Query(None, description="Filter by connector ID"),
    session_id: Optional[int] = Query(None, description="Filter by session ID"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    start_date: Optional[datetime] = Query(None, description="Filter by start date (from)"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date (to)"),
    limit: int = Query(100, description="Limit number of results"),
    offset: int = Query(0, description="Offset for pagination"),
    order_by: str = Query("EventsDataDateTime", description="Order by field"),
    sort_direction: str = Query("DESC", description="Sort direction (ASC/DESC)")
):
    """Get a list of events with optional filtering."""
    try:
        query = "SELECT * FROM EventsData"
        params = []
        
        # Build WHERE clause for filters
        filters = []
        
        if company_id is not None:
            filters.append("EventsDataCompanyId = ?")
            params.append(company_id)
            
        if site_id is not None:
            filters.append("EventsDataSiteId = ?")
            params.append(site_id)
            
        if charger_id is not None:
            filters.append("EventsDataChargerId = ?")
            params.append(charger_id)
            
        if connector_id is not None:
            filters.append("EventsDataConnectorId = ?")
            params.append(connector_id)
            
        if session_id is not None:
            filters.append("EventsDataSessionId = ?")
            params.append(session_id)
            
        if event_type is not None:
            filters.append("EventsDataType = ?")
            params.append(event_type)
            
        if start_date is not None:
            filters.append("EventsDataDateTime >= ?")
            params.append(start_date.isoformat())
            
        if end_date is not None:
            filters.append("EventsDataDateTime <= ?")
            params.append(end_date.isoformat())
            
        if filters:
            query += f" WHERE {' AND '.join(filters)}"
        
        # Validate sort direction
        sort_direction = sort_direction.upper()
        if sort_direction not in ["ASC", "DESC"]:
            sort_direction = "DESC"
            
        query += f" ORDER BY {order_by} {sort_direction} LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        events = execute_query(query, tuple(params))
        return events
    except Exception as e:
        logger.error(f"Error getting events: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/{event_id}", response_model=EventData)
async def get_event(event_id: int):
    """Get details of a specific event by ID."""
    try:
        event = execute_query(
            "SELECT * FROM EventsData WHERE EventsDataNumber = ?", 
            (event_id,)
        )
        
        if not event:
            raise HTTPException(status_code=404, detail=f"Event with ID {event_id} not found")
            
        return event[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting event {event_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# Hierarchical Access Endpoints

@company_router.get("/{company_id}/events", response_model=List[EventData])
async def get_company_events(
    company_id: int,
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    start_date: Optional[datetime] = Query(None, description="Filter by start date (from)"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date (to)"),
    limit: int = Query(100, description="Limit number of results"),
    offset: int = Query(0, description="Offset for pagination")
):
    """Get all events for a specific company."""
    try:
        # Check if company exists
        company = execute_query("SELECT 1 FROM Companies WHERE CompanyId = ?", (company_id,))
        if not company:
            raise HTTPException(status_code=404, detail=f"Company with ID {company_id} not found")
            
        query = "SELECT * FROM EventsData WHERE EventsDataCompanyId = ?"
        params = [company_id]
        
        if event_type is not None:
            query += " AND EventsDataType = ?"
            params.append(event_type)
            
        if start_date is not None:
            query += " AND EventsDataDateTime >= ?"
            params.append(start_date.isoformat())
            
        if end_date is not None:
            query += " AND EventsDataDateTime <= ?"
            params.append(end_date.isoformat())
            
        query += " ORDER BY EventsDataDateTime DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        events = execute_query(query, tuple(params))
        return events
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting events for company {company_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@site_router.get("/{site_id}/events", response_model=List[EventData])
async def get_site_events(
    site_id: int,
    company_id: int = Query(..., description="Company ID"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    charger_id: Optional[int] = Query(None, description="Filter by charger ID"),
    start_date: Optional[datetime] = Query(None, description="Filter by start date (from)"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date (to)"),
    limit: int = Query(100, description="Limit number of results"),
    offset: int = Query(0, description="Offset for pagination")
):
    """Get all events for a specific site."""
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
            
        query = "SELECT * FROM EventsData WHERE EventsDataSiteId = ? AND EventsDataCompanyId = ?"
        params = [site_id, company_id]
        
        if event_type is not None:
            query += " AND EventsDataType = ?"
            params.append(event_type)
            
        if charger_id is not None:
            query += " AND EventsDataChargerId = ?"
            params.append(charger_id)
            
        if start_date is not None:
            query += " AND EventsDataDateTime >= ?"
            params.append(start_date.isoformat())
            
        if end_date is not None:
            query += " AND EventsDataDateTime <= ?"
            params.append(end_date.isoformat())
            
        query += " ORDER BY EventsDataDateTime DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        events = execute_query(query, tuple(params))
        return events
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting events for site {site_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@charger_router.get("/{charger_id}/events", response_model=List[EventData])
async def get_charger_events(
    charger_id: int,
    company_id: int = Query(..., description="Company ID"),
    site_id: int = Query(..., description="Site ID"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    connector_id: Optional[int] = Query(None, description="Filter by connector ID"),
    start_date: Optional[datetime] = Query(None, description="Filter by start date (from)"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date (to)"),
    limit: int = Query(100, description="Limit number of results"),
    offset: int = Query(0, description="Offset for pagination")
):
    """Get all events for a specific charger."""
    try:
        # Check if charger exists
        charger = execute_query(
            "SELECT 1 FROM Chargers WHERE ChargerId = ? AND ChargerCompanyId = ? AND ChargerSiteId = ?", 
            (charger_id, company_id, site_id)
        )
        
        if not charger:
            raise HTTPException(status_code=404, detail=f"Charger with ID {charger_id} not found")
            
        query = """
            SELECT * FROM EventsData 
            WHERE EventsDataChargerId = ? AND EventsDataCompanyId = ? AND EventsDataSiteId = ?
        """
        params = [charger_id, company_id, site_id]
        
        if event_type is not None:
            query += " AND EventsDataType = ?"
            params.append(event_type)
            
        if connector_id is not None:
            query += " AND EventsDataConnectorId = ?"
            params.append(connector_id)
            
        if start_date is not None:
            query += " AND EventsDataDateTime >= ?"
            params.append(start_date.isoformat())
            
        if end_date is not None:
            query += " AND EventsDataDateTime <= ?"
            params.append(end_date.isoformat())
            
        query += " ORDER BY EventsDataDateTime DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        events = execute_query(query, tuple(params))
        return events
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting events for charger {charger_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@session_router.get("/{session_id}/events", response_model=List[EventData])
async def get_session_events(
    session_id: int,
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    limit: int = Query(100, description="Limit number of results"),
    offset: int = Query(0, description="Offset for pagination")
):
    """Get all events for a specific charge session."""
    try:
        # Check if session exists
        session = execute_query(
            "SELECT 1 FROM ChargeSessions WHERE ChargeSessionId = ?", 
            (session_id,)
        )
        
        if not session:
            raise HTTPException(status_code=404, detail=f"Session with ID {session_id} not found")
            
        query = "SELECT * FROM EventsData WHERE EventsDataSessionId = ?"
        params = [session_id]
        
        if event_type is not None:
            query += " AND EventsDataType = ?"
            params.append(event_type)
            
        query += " ORDER BY EventsDataDateTime ASC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        events = execute_query(query, tuple(params))
        return events
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting events for session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# Additional utility endpoints for hierarchical access

@company_router.get("/{company_id}/events/summary", response_model=EventSummary)
async def get_company_events_summary(
    company_id: int,
    start_date: Optional[datetime] = Query(None, description="Filter by start date (from)"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date (to)")
):
    """Get event summary statistics for a company."""
    try:
        # Check if company exists
        company = execute_query("SELECT 1 FROM Companies WHERE CompanyId = ?", (company_id,))
        if not company:
            raise HTTPException(status_code=404, detail=f"Company with ID {company_id} not found")
            
        # Build base query
        base_where = "WHERE EventsDataCompanyId = ?"
        params = [company_id]
        
        if start_date is not None:
            base_where += " AND EventsDataDateTime >= ?"
            params.append(start_date.isoformat())
            
        if end_date is not None:
            base_where += " AND EventsDataDateTime <= ?"
            params.append(end_date.isoformat())
        
        # Get total count
        total_count = execute_query(
            f"SELECT COUNT(*) as total FROM EventsData {base_where}",
            tuple(params)
        )
        
        # Get event type breakdown
        event_types = execute_query(
            f"SELECT EventsDataType, COUNT(*) as count FROM EventsData {base_where} GROUP BY EventsDataType",
            tuple(params)
        )
        
        # Get date range
        date_range = execute_query(
            f"SELECT MIN(EventsDataDateTime) as earliest, MAX(EventsDataDateTime) as latest FROM EventsData {base_where}",
            tuple(params)
        )
        
        # Get latest event
        latest_event = execute_query(
            f"SELECT MAX(EventsDataDateTime) as latest FROM EventsData {base_where}",
            tuple(params)
        )
        
        return EventSummary(
            total_events=total_count[0]["total"] if total_count else 0,
            event_types={et["EventsDataType"]: et["count"] for et in event_types},
            date_range={
                "earliest": date_range[0]["earliest"] if date_range and date_range[0]["earliest"] else None,
                "latest": date_range[0]["latest"] if date_range and date_range[0]["latest"] else None
            },
            latest_event=datetime.fromisoformat(latest_event[0]["latest"]) if latest_event and latest_event[0]["latest"] else None
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting event summary for company {company_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@site_router.get("/{site_id}/events/by_type", response_model=List[EventTypeStats])
async def get_site_events_by_type(
    site_id: int,
    company_id: int = Query(..., description="Company ID"),
    start_date: Optional[datetime] = Query(None, description="Filter by start date (from)"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date (to)")
):
    """Get event statistics by type for a specific site."""
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
            SELECT 
                EventsDataType as event_type,
                COUNT(*) as count,
                MIN(EventsDataDateTime) as earliest_occurrence,
                MAX(EventsDataDateTime) as latest_occurrence
            FROM EventsData 
            WHERE EventsDataSiteId = ? AND EventsDataCompanyId = ?
        """
        params = [site_id, company_id]
        
        if start_date is not None:
            query += " AND EventsDataDateTime >= ?"
            params.append(start_date.isoformat())
            
        if end_date is not None:
            query += " AND EventsDataDateTime <= ?"
            params.append(end_date.isoformat())
            
        query += " GROUP BY EventsDataType ORDER BY count DESC"
        
        stats = execute_query(query, tuple(params))
        
        result = []
        for stat in stats:
            result.append(EventTypeStats(
                event_type=stat["event_type"],
                count=stat["count"],
                earliest_occurrence=datetime.fromisoformat(stat["earliest_occurrence"]) if stat["earliest_occurrence"] else None,
                latest_occurrence=datetime.fromisoformat(stat["latest_occurrence"]) if stat["latest_occurrence"] else None
            ))
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting event type stats for site {site_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@charger_router.get("/{charger_id}/events/latest", response_model=List[EventData])
async def get_charger_latest_events(
    charger_id: int,
    company_id: int = Query(..., description="Company ID"),
    site_id: int = Query(..., description="Site ID"),
    hours: int = Query(24, description="Number of hours to look back"),
    limit: int = Query(50, description="Limit number of results")
):
    """Get latest events for a specific charger within specified hours."""
    try:
        # Check if charger exists
        charger = execute_query(
            "SELECT 1 FROM Chargers WHERE ChargerId = ? AND ChargerCompanyId = ? AND ChargerSiteId = ?", 
            (charger_id, company_id, site_id)
        )
        
        if not charger:
            raise HTTPException(status_code=404, detail=f"Charger with ID {charger_id} not found")
        
        # Calculate cutoff time
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        query = """
            SELECT * FROM EventsData 
            WHERE EventsDataChargerId = ? AND EventsDataCompanyId = ? AND EventsDataSiteId = ?
            AND EventsDataDateTime >= ?
            ORDER BY EventsDataDateTime DESC
            LIMIT ?
        """
        
        events = execute_query(
            query, 
            (charger_id, company_id, site_id, cutoff_time.isoformat(), limit)
        )
        
        return events
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting latest events for charger {charger_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")