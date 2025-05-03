from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional, Dict, Any
from datetime import datetime, time
import logging

from app.models.charger import Charger, ChargerCreate, ChargerUpdate, Connector, ConnectorCreate, ConnectorUpdate
from app.db.database import execute_query, execute_insert, execute_update, execute_delete
from app.ws.connection_manager import manager

router = APIRouter(prefix="/api/v1/chargers", tags=["chargers"])
site_router = APIRouter(prefix="/api/v1/sites", tags=["sites"])

logger = logging.getLogger("ocpp.chargers")

@router.get("/", response_model=List[Charger])
async def get_chargers(
    company_id: Optional[int] = Query(None, description="Filter by company ID"),
    site_id: Optional[int] = Query(None, description="Filter by site ID"),
    enabled: Optional[bool] = Query(None, description="Filter by enabled status"),
    online: Optional[bool] = Query(None, description="Filter by online status")
):
    """Get a list of all chargers with optional filtering."""
    try:
        query = "SELECT * FROM Chargers"
        params = []
        
        # Build WHERE clause for filters
        filters = []
        
        if company_id is not None:
            filters.append("ChargerCompanyId = ?")
            params.append(company_id)
            
        if site_id is not None:
            filters.append("ChargerSiteId = ?")
            params.append(site_id)
            
        if enabled is not None:
            filters.append("ChargerEnabled = ?")
            params.append(1 if enabled else 0)
            
        if online is not None:
            filters.append("ChargerIsOnline = ?")
            params.append(1 if online else 0)
            
        if filters:
            query += f" WHERE {' AND '.join(filters)}"
            
        query += " ORDER BY ChargerName"
        
        chargers = execute_query(query, tuple(params) if params else None)
        return chargers
    except Exception as e:
        logger.error(f"Error getting chargers: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/{charger_id}", response_model=Charger)
async def get_charger(charger_id: int, company_id: int, site_id: int):
    """Get details of a specific charger by ID."""
    try:
    
        charger = execute_query(
            "SELECT * FROM Chargers WHERE ChargerId = ? AND ChargerCompanyId = ? AND ChargerSiteId = ?", 
            (charger_id, company_id, site_id)
        )
        
        if not charger:
            raise HTTPException(status_code=404, detail=f"Charger with ID {charger_id} not found")
            
        return charger[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting charger {charger_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.post("/", response_model=Charger, status_code=201)
async def create_charger(charger: ChargerCreate):
    """Create a new charger."""
    try:
        # Check if company exists
        company = execute_query(
            "SELECT 1 FROM Companies WHERE CompanyId = ?", 
            (charger.ChargerCompanyId,)
        )
        
        if not company:
            raise HTTPException(status_code=404, detail=f"Company with ID {charger.ChargerCompanyId} not found")
            
        # Check if site exists
        site = execute_query(
            "SELECT 1 FROM Sites WHERE SiteId = ? AND SiteCompanyID = ?", 
            (charger.ChargerSiteId, charger.ChargerCompanyId)
        )
        
        if not site:
            raise HTTPException(
                status_code=404, 
                detail=f"Site with ID {charger.ChargerSiteId} not found or does not belong to company {charger.ChargerCompanyId}"
            )
            
        # Check if payment method exists if provided
        if charger.ChargerPaymentMethodId:
            payment_method = execute_query(
                "SELECT 1 FROM PaymentMethods WHERE PaymentMethodId = ?", 
                (charger.ChargerPaymentMethodId,)
            )
            
            if not payment_method:
                raise HTTPException(status_code=404, detail=f"Payment method with ID {charger.ChargerPaymentMethodId} not found")
        
        # Check if charger already exists
        existing_charger = execute_query(
            "SELECT 1 FROM Chargers WHERE ChargerId = ? AND ChargerCompanyId = ? AND ChargerSiteId = ?",
            (charger.ChargerId, charger.ChargerCompanyId, charger.ChargerSiteId)
        )
        
        if existing_charger:
            raise HTTPException(
                status_code=409, 
                detail=f"Charger with ID {charger.ChargerId} already exists for company {charger.ChargerCompanyId} and site {charger.ChargerSiteId}"
            )
            
        now = datetime.now().isoformat()
        
        # Insert new charger
        execute_insert(
            """
            INSERT INTO Chargers (
                ChargerId, ChargerCompanyId, ChargerSiteId, ChargerName, ChargerEnabled,
                ChargerBrand, ChargerModel, ChargerType, ChargerSerial, ChargerMeter,
                ChargerMeterSerial, ChargerPincode, ChargerWsURL, ChargerICCID, 
                ChargerAvailability, ChargerIsOnline, ChargerAccessType, 
                ChargerActive24x7, ChargerGeoCoord, ChargerPaymentMethodId, 
                ChargerPhoto, ChargerFirmwareVersion, ChargerCreated, ChargerUpdated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                charger.ChargerId,
                charger.ChargerCompanyId,
                charger.ChargerSiteId,
                charger.ChargerName,
                1 if charger.ChargerEnabled else 0,
                charger.ChargerBrand,
                charger.ChargerModel,
                charger.ChargerType,
                charger.ChargerSerial,
                charger.ChargerMeter,
                charger.ChargerMeterSerial,
                charger.ChargerPincode,
                charger.ChargerWsURL,
                charger.ChargerICCID,
                charger.ChargerAvailability,
                1 if charger.ChargerIsOnline else 0,
                charger.ChargerAccessType,
                1 if charger.ChargerActive24x7 else 0,
                charger.ChargerGeoCoord,
                charger.ChargerPaymentMethodId,
                charger.ChargerPhoto,
                charger.ChargerFirmwareVersion,
                now,
                now
            )
        )
        
        # Return the created charger
        return await get_charger(charger.ChargerId, charger.ChargerCompanyId, charger.ChargerSiteId)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating charger: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.put("/{charger_id}", response_model=Charger)
async def update_charger(charger_id: int, company_id: int, site_id: int, charger: ChargerUpdate):
    """Update an existing charger."""
    try:
        # Check if charger exists
        existing = execute_query(
            "SELECT 1 FROM Chargers WHERE ChargerId = ? AND ChargerCompanyId = ? AND ChargerSiteId = ?", 
            (charger_id, company_id, site_id)
        )
        if not existing:
            raise HTTPException(status_code=404, detail=f"Charger with ID {charger_id} not found")
        
        # Check if payment method exists if provided
        if charger.ChargerPaymentMethodId:
            payment_method = execute_query(
                "SELECT 1 FROM PaymentMethods WHERE PaymentMethodId = ?", 
                (charger.ChargerPaymentMethodId,)
            )
            
            if not payment_method:
                raise HTTPException(status_code=404, detail=f"Payment method with ID {charger.ChargerPaymentMethodId} not found")
        
        # Build update query dynamically based on provided fields
        update_fields = []
        params = []
        
        for field, value in charger.model_dump(exclude_unset=True).items():
            if value is not None:
                # Convert boolean to integer for SQLite
                if isinstance(value, bool):
                    value = 1 if value else 0
                # Convert datetime.time to string
                if isinstance(value, time):
                    value = value.strftime('%H:%M:%S')
                update_fields.append(f"{field} = ?")
                params.append(value)
                
        if not update_fields:
            # No fields to update
            return await get_charger(charger_id, company_id, site_id)
            
        # Add ChargerUpdated field
        update_fields.append("ChargerUpdated = ?")
        params.append(datetime.now().isoformat())
        
        # Add charger_id, company_id, site_id to params
        params.extend([charger_id, company_id, site_id])
        
        # Execute update
        execute_update(
            f"""UPDATE Chargers SET {', '.join(update_fields)} 
               WHERE ChargerId = ? AND ChargerCompanyId = ? AND ChargerSiteId = ?""",
            tuple(params)
        )
        
        # Return updated charger
        return await get_charger(charger_id, company_id, site_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating charger {charger_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.delete("/{charger_id}", status_code=204)
async def delete_charger(charger_id: int, company_id: int, site_id: int):
    """Delete a charger."""
    try:
        # Check if charger exists
        existing = execute_query(
            "SELECT 1 FROM Chargers WHERE ChargerId = ? AND ChargerCompanyId = ? AND ChargerSiteId = ?", 
            (charger_id, company_id, site_id)
        )
        if not existing:
            raise HTTPException(status_code=404, detail=f"Charger with ID {charger_id} not found")
            
        # Delete charger
        rows_deleted = execute_delete(
            "DELETE FROM Chargers WHERE ChargerId = ? AND ChargerCompanyId = ? AND ChargerSiteId = ?", 
            (charger_id, company_id, site_id)
        )
        
        if rows_deleted == 0:
            raise HTTPException(status_code=500, detail=f"Failed to delete charger {charger_id}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting charger {charger_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/{charger_id}/status", response_model=Dict[str, Any])
async def get_charger_status(charger_id: int, company_id: int, site_id: int):
    """Get current status of a charger including connectivity state."""
    try:
        # Check if charger exists in database
        charger = execute_query(
            "SELECT ChargerId, ChargerName, ChargerEnabled, ChargerIsOnline, ChargerLastConn, ChargerLastHeartbeat FROM Chargers WHERE ChargerId = ? AND ChargerCompanyId = ? AND ChargerSiteId = ?", 
            (charger_id, company_id, site_id)
        )
        
        if not charger:
            raise HTTPException(status_code=404, detail=f"Charger with ID {charger_id} not found")
        
        # Check if currently connected to OCPP server
        active_connections = manager.get_charge_points()
        connected = str(charger_id) in active_connections
        
        # Get connection stats if connected
        connection_stats = {}
        if connected:
            stats = manager.get_connection_stats()
            if str(charger_id) in stats:
                connection_stats = stats[str(charger_id)]
        
        # Get latest status notifications for connectors
        connector_statuses = execute_query(
            """
            SELECT c.ConnectorId, c.ConnectorStatus, c.ConnectorEnabled, c.ConnectorType, 
                   e.EventsDataDateTime as last_status_update
            FROM Connectors c
            LEFT JOIN (
                SELECT EventsDataConnectorId, MAX(EventsDataDateTime) as max_date
                FROM EventsData
                WHERE EventsDataChargerId = ? AND EventsDataType = 'StatusNotification'
                GROUP BY EventsDataConnectorId
            ) latest ON c.ConnectorId = latest.EventsDataConnectorId
            LEFT JOIN EventsData e ON latest.EventsDataConnectorId = e.EventsDataConnectorId 
                                   AND latest.max_date = e.EventsDataDateTime
            WHERE c.ConnectorChargerId = ? AND c.ConnectorCompanyId = ? AND c.ConnectorSiteId = ?
            """,
            (charger_id, charger_id, company_id, site_id)
        )
        
        return {
            "charger_id": charger_id,
            "company_id": company_id,
            "site_id": site_id,
            "name": charger[0]["ChargerName"],
            "enabled": bool(charger[0]["ChargerEnabled"]),
            "online_in_db": bool(charger[0]["ChargerIsOnline"]),
            "connected_to_server": connected,
            "last_connection": charger[0]["ChargerLastConn"],
            "last_heartbeat": charger[0]["ChargerLastHeartbeat"],
            "connection_stats": connection_stats,
            "connectors": connector_statuses
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting charger status {charger_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/{charger_id}/connectors", response_model=List[Connector])
async def get_charger_connectors(charger_id: int, company_id: int, site_id: int):
    """Get all connectors for a specific charger."""
    try:
        # Check if charger exists
        charger = execute_query(
            "SELECT 1 FROM Chargers WHERE ChargerId = ? AND ChargerCompanyId = ? AND ChargerSiteId = ?", 
            (charger_id, company_id, site_id)
        )
        
        if not charger:
            raise HTTPException(status_code=404, detail=f"Charger with ID {charger_id} not found")
            
        # Get connectors
        connectors = execute_query(
            """
            SELECT * FROM Connectors 
            WHERE ConnectorChargerId = ? AND ConnectorCompanyId = ? AND ConnectorSiteId = ?
            ORDER BY ConnectorId
            """, 
            (charger_id, company_id, site_id)
        )
        
        return connectors
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting connectors for charger {charger_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.post("/{charger_id}/connectors", response_model=Connector, status_code=201)
async def create_connector(charger_id: int, company_id: int, site_id: int, connector: ConnectorCreate):
    """Create a new connector for a charger."""
    try:
        # Check if charger exists
        charger = execute_query(
            "SELECT 1 FROM Chargers WHERE ChargerId = ? AND ChargerCompanyId = ? AND ChargerSiteId = ?", 
            (charger_id, company_id, site_id)
        )
        
        if not charger:
            raise HTTPException(status_code=404, detail=f"Charger with ID {charger_id} not found")
            
        # Check if connector already exists
        existing_connector = execute_query(
            """
            SELECT 1 FROM Connectors
            WHERE ConnectorId = ? AND ConnectorChargerId = ? AND ConnectorCompanyId = ? AND ConnectorSiteId = ?
            """,
            (connector.ConnectorId, charger_id, company_id, site_id)
        )
        
        if existing_connector:
            raise HTTPException(
                status_code=409, 
                detail=f"Connector with ID {connector.ConnectorId} already exists for charger {charger_id}"
            )
            
        now = datetime.now().isoformat()
        
        # Insert new connector
        execute_insert(
            """
            INSERT INTO Connectors (
                ConnectorId, ConnectorCompanyId, ConnectorSiteId, ConnectorChargerId,
                ConnectorType, ConnectorEnabled, ConnectorStatus, ConnectorMaxVolt,
                ConnectorMaxAmp, ConnectorCreated, ConnectorUpdated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                connector.ConnectorId,
                company_id,
                site_id,
                charger_id,
                connector.ConnectorType,
                1 if connector.ConnectorEnabled else 0,
                connector.ConnectorStatus,
                connector.ConnectorMaxVolt,
                connector.ConnectorMaxAmp,
                now,
                now
            )
        )
        
        # Return the created connector
        connector_result = execute_query(
            """
            SELECT * FROM Connectors
            WHERE ConnectorId = ? AND ConnectorChargerId = ? AND ConnectorCompanyId = ? AND ConnectorSiteId = ?
            """,
            (connector.ConnectorId, charger_id, company_id, site_id)
        )
        
        return connector_result[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating connector for charger {charger_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@site_router.get("/{site_id}/chargers", response_model=List[Charger])
async def get_site_chargers(
    site_id: int,
    company_id: int = Query(..., description="Company ID"),
    enabled: Optional[bool] = Query(None, description="Filter by enabled status"),
    online: Optional[bool] = Query(None, description="Filter by online status")
):
    """Get all chargers for a specific site."""
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
            
        query = "SELECT * FROM Chargers WHERE ChargerSiteId = ? AND ChargerCompanyId = ?"
        params = [site_id, company_id]
        
        if enabled is not None:
            query += " AND ChargerEnabled = ?"
            params.append(1 if enabled else 0)
            
        if online is not None:
            query += " AND ChargerIsOnline = ?"
            params.append(1 if online else 0)
            
        query += " ORDER BY ChargerName"
        
        chargers = execute_query(query, tuple(params))
        return chargers
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting chargers for site {site_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")