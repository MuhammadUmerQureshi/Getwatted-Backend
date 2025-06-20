from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional, Dict, Any
from datetime import datetime, time
import logging

from app.models.charger import Charger, ChargerCreate, ChargerUpdate, Connector, ConnectorCreate, ConnectorUpdate
from app.models.auth import UserInToken
from app.db.database import execute_query, execute_insert, execute_update, execute_delete
from app.ws.connection_manager import manager
from app.dependencies.auth import (
    require_role,
    get_current_user,
    require_company_access,
    require_admin_or_higher
)
from app.services.auth_service import AuthService
from fastapi import status

router = APIRouter(prefix="/api/v1/chargers", tags=["CHARGERS"])
site_router = APIRouter(prefix="/api/v1/sites", tags=["SITES"])

logger = logging.getLogger("ocpp.chargers")

@router.get("/", response_model=List[Charger])
async def get_chargers(
    company_id: Optional[int] = Query(None, description="Filter by company ID"),
    site_id: Optional[int] = Query(None, description="Filter by site ID"),
    enabled: Optional[bool] = Query(None, description="Filter by enabled status"),
    online: Optional[bool] = Query(None, description="Filter by online status"),
    user: UserInToken = Depends(require_admin_or_higher)
):
    """
    Get a list of all chargers with optional filtering.
    
    - SuperAdmin: Can see all chargers
    - Admin: Can only see chargers from their company
    - Driver: Not allowed to access this endpoint
    """
    try:
        query = "SELECT * FROM Chargers"
        params = []
        filters = []
        
        # Apply company filter based on role
        if user.role.value != "SuperAdmin":
            company_id = user.company_id
        
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
            query += " WHERE " + " AND ".join(filters)
            
        query += " ORDER BY ChargerName"
        
        chargers = execute_query(query, tuple(params))
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
async def create_charger(
    charger: ChargerCreate,
    user: UserInToken = Depends(require_admin_or_higher)
):
    """
    Create a new charger.
    
    - SuperAdmin: Can create chargers for any company
    - Admin: Can only create chargers for their company
    - Driver: Not allowed to access this endpoint
    """
    try:
        # Validate company access
        if user.role.value != "SuperAdmin":
            if charger.ChargerCompanyId != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only create chargers for your own company"
                )
        
        # Check if company exists
        company = execute_query(
            "SELECT 1 FROM Companies WHERE CompanyId = ?",
            (charger.ChargerCompanyId,)
        )
        if not company:
            raise HTTPException(
                status_code=404,
                detail=f"Company with ID {charger.ChargerCompanyId} not found"
            )
            
        # Check if site exists and belongs to company
        if charger.ChargerSiteId:
            site = execute_query(
                "SELECT 1 FROM Sites WHERE SiteId = ? AND SiteCompanyID = ?",
                (charger.ChargerSiteId, charger.ChargerCompanyId)
            )
            if not site:
                raise HTTPException(
                    status_code=404,
                    detail=f"Site with ID {charger.ChargerSiteId} not found or does not belong to company {charger.ChargerCompanyId}"
                )
        
        # Check if charger name already exists within the site
        existing_charger = execute_query(
            "SELECT 1 FROM Chargers WHERE ChargerCompanyId = ? AND ChargerSiteId = ? AND ChargerName = ?",
            (charger.ChargerCompanyId, charger.ChargerSiteId, charger.ChargerName)
        )
        
        if existing_charger:
            raise HTTPException(
                status_code=409, 
                detail=f"Charger with name '{charger.ChargerName}' already exists in site {charger.ChargerSiteId}"
            )
            
        # Check if charger ID already exists within the site
        existing_charger_id = execute_query(
            "SELECT 1 FROM Chargers WHERE ChargerId = ? AND ChargerCompanyId = ? AND ChargerSiteId = ?",
            (charger.ChargerId, charger.ChargerCompanyId, charger.ChargerSiteId)
        )
        
        if existing_charger_id:
            raise HTTPException(
                status_code=409, 
                detail=f"Charger with ID {charger.ChargerId} already exists for company {charger.ChargerCompanyId} and site {charger.ChargerSiteId}"
            )
            
        # Check if payment method exists if provided
        if charger.ChargerPaymentMethodId:
            payment_method = execute_query(
                "SELECT 1 FROM PaymentMethods WHERE PaymentMethodId = ?", 
                (charger.ChargerPaymentMethodId,)
            )
            
            if not payment_method:
                raise HTTPException(status_code=404, detail=f"Payment method with ID {charger.ChargerPaymentMethodId} not found")
            
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
                charger.ChargerEnabled,
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
                charger.ChargerIsOnline,
                charger.ChargerAccessType,
                charger.ChargerActive24x7,
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
        # Handle database constraint violations
        if "UNIQUE constraint failed" in str(e):
            if "ChargerName" in str(e):
                raise HTTPException(
                    status_code=409, 
                    detail=f"Charger with name '{charger.ChargerName}' already exists in site {charger.ChargerSiteId}"
                )
        logger.error(f"Error creating charger: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.put("/{charger_id}", response_model=Charger)
async def update_charger(
    charger_id: int,
    charger_update: ChargerUpdate,
    user: UserInToken = Depends(require_admin_or_higher)
):
    """
    Update a charger.
    
    - SuperAdmin: Can update any charger
    - Admin: Can only update chargers from their company
    - Driver: Not allowed to access this endpoint
    """
    try:
        # Get current charger
        current_charger = execute_query(
            "SELECT * FROM Chargers WHERE ChargerId = ?",
            (charger_id,)
        )
        
        if not current_charger:
            raise HTTPException(
                status_code=404,
                detail=f"Charger with ID {charger_id} not found"
            )
            
        # Check company access
        if user.role.value != "SuperAdmin":
            if current_charger[0]["ChargerCompanyId"] != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only update chargers from your company"
                )
            
            # Prevent changing company for non-superadmins
            if charger_update.ChargerCompanyId and charger_update.ChargerCompanyId != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You cannot change a charger's company"
                )
            
            # Validate site belongs to company if changing
            if charger_update.ChargerSiteId:
                site = execute_query(
                    "SELECT 1 FROM Sites WHERE SiteId = ? AND SiteCompanyID = ?",
                    (charger_update.ChargerSiteId, user.company_id)
                )
                if not site:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Site with ID {charger_update.ChargerSiteId} not found or does not belong to your company"
                    )
        
        # Update charger
        now = datetime.now().isoformat()
        execute_update(
            """
            UPDATE Chargers SET
                ChargerCompanyId = ?,
                ChargerSiteId = ?,
                ChargerName = ?,
                ChargerEnabled = ?,
                ChargerBrand = ?,
                ChargerModel = ?,
                ChargerType = ?,
                ChargerSerial = ?,
                ChargerMeter = ?,
                ChargerMeterSerial = ?,
                ChargerPincode = ?,
                ChargerWsURL = ?,
                ChargerICCID = ?,
                ChargerAvailability = ?,
                ChargerIsOnline = ?,
                ChargerAccessType = ?,
                ChargerActive24x7 = ?,
                ChargerGeoCoord = ?,
                ChargerPaymentMethodId = ?,
                ChargerPhoto = ?,
                ChargerFirmwareVersion = ?,
                ChargerUpdated = ?
            WHERE ChargerId = ?
            """,
            (
                charger_update.ChargerCompanyId or current_charger[0]["ChargerCompanyId"],
                charger_update.ChargerSiteId or current_charger[0]["ChargerSiteId"],
                charger_update.ChargerName or current_charger[0]["ChargerName"],
                charger_update.ChargerEnabled if charger_update.ChargerEnabled is not None else current_charger[0]["ChargerEnabled"],
                charger_update.ChargerBrand or current_charger[0]["ChargerBrand"],
                charger_update.ChargerModel or current_charger[0]["ChargerModel"],
                charger_update.ChargerType or current_charger[0]["ChargerType"],
                charger_update.ChargerSerial or current_charger[0]["ChargerSerial"],
                charger_update.ChargerMeter or current_charger[0]["ChargerMeter"],
                charger_update.ChargerMeterSerial or current_charger[0]["ChargerMeterSerial"],
                charger_update.ChargerPincode or current_charger[0]["ChargerPincode"],
                charger_update.ChargerWsURL or current_charger[0]["ChargerWsURL"],
                charger_update.ChargerICCID or current_charger[0]["ChargerICCID"],
                charger_update.ChargerAvailability or current_charger[0]["ChargerAvailability"],
                charger_update.ChargerIsOnline if charger_update.ChargerIsOnline is not None else current_charger[0]["ChargerIsOnline"],
                charger_update.ChargerAccessType or current_charger[0]["ChargerAccessType"],
                charger_update.ChargerActive24x7 if charger_update.ChargerActive24x7 is not None else current_charger[0]["ChargerActive24x7"],
                charger_update.ChargerGeoCoord or current_charger[0]["ChargerGeoCoord"],
                charger_update.ChargerPaymentMethodId or current_charger[0]["ChargerPaymentMethodId"],
                charger_update.ChargerPhoto or current_charger[0]["ChargerPhoto"],
                charger_update.ChargerFirmwareVersion or current_charger[0]["ChargerFirmwareVersion"],
                now,
                charger_id
            )
        )
        
        # Return updated charger
        updated_charger = execute_query(
            "SELECT * FROM Chargers WHERE ChargerId = ?",
            (charger_id,)
        )
        
        logger.info(f"✅ Charger updated: {charger_id} by {user.email}")
        return updated_charger[0]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating charger: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.delete("/{charger_id}", status_code=204)
async def delete_charger(
    charger_id: int,
    user: UserInToken = Depends(require_admin_or_higher)
):
    """
    Delete a charger.
    
    - SuperAdmin: Can delete any charger
    - Admin: Can only delete chargers from their company
    - Driver: Not allowed to access this endpoint
    """
    try:
        # Get current charger
        current_charger = execute_query(
            "SELECT * FROM Chargers WHERE ChargerId = ?",
            (charger_id,)
        )
        
        if not current_charger:
            raise HTTPException(
                status_code=404,
                detail=f"Charger with ID {charger_id} not found"
            )
            
        # Check company access
        if user.role.value != "SuperAdmin":
            if current_charger[0]["ChargerCompanyId"] != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only delete chargers from your company"
                )
        
        # Delete charger
        execute_delete(
            "DELETE FROM Chargers WHERE ChargerId = ?",
            (charger_id,)
        )
        
        logger.info(f"✅ Charger deleted: {charger_id} by {user.email}")
        return {"message": f"Charger {charger_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting charger: {str(e)}")
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

@site_router.get("/{site_id}/chargers", response_model=List[Charger])
async def get_site_chargers(
    site_id: int,
    company_id: int = Query(..., description="Company ID"),
    enabled: Optional[bool] = Query(None, description="Filter by enabled status"),
    user: UserInToken = Depends(require_admin_or_higher)
):
    """
    Get all chargers for a specific site.
    
    - SuperAdmin: Can see chargers from any company
    - Admin: Can only see chargers from their company
    - Driver: Not allowed to access this endpoint
    """
    try:
        # Check company access
        if not AuthService.check_company_access(user, company_id):
            logger.warning(f"⚠️ Company access denied: User {user.email} (company {user.company_id}) tried to access company {company_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied to company {company_id}"
            )

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
            
        query = "SELECT * FROM Chargers WHERE ChargerSiteId = ? AND ChargerCompanyId = ?"
        params = [site_id, company_id]
        
        if enabled is not None:
            query += " AND ChargerEnabled = ?"
            params.append(1 if enabled else 0)
            
        query += " ORDER BY ChargerName"
        
        chargers = execute_query(query, tuple(params))
        return chargers
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting chargers for site {site_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")