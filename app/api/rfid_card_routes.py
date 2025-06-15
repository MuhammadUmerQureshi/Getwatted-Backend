# app/api/rfid_card_routes.py
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional
from datetime import datetime
import logging

from app.models.rfid_card import RFIDCard, RFIDCardCreate, RFIDCardUpdate
from app.models.auth import UserInToken
from app.db.database import execute_query, execute_insert, execute_update, execute_delete
from app.dependencies.auth import (
    require_role,
    get_current_user,
    require_admin_or_higher,
    check_company_access
)

router = APIRouter(prefix="/api/v1/rfid_cards", tags=["RFID CARDS"])
company_router = APIRouter(prefix="/api/v1/companies", tags=["COMPANIES"])
driver_router = APIRouter(prefix="/api/v1/drivers", tags=["DRIVERS"])

logger = logging.getLogger("ocpp.rfid_cards")

@router.get("/", response_model=List[RFIDCard])
async def get_rfid_cards(
    company_id: Optional[int] = Query(None, description="Filter by company ID"),
    driver_id: Optional[int] = Query(None, description="Filter by driver ID"),
    enabled: Optional[bool] = Query(None, description="Filter by enabled status"),
    user: UserInToken = Depends(require_admin_or_higher)
):
    """
    Get a list of all RFID cards with optional filtering.
    
    - SuperAdmin: Can see all RFID cards
    - Admin: Can only see RFID cards from their company
    - Driver: Not allowed to access this endpoint
    """
    try:
        query = "SELECT * FROM RFIDCards"
        params = []
        filters = []
        
        # Apply company filter based on role
        if user.role.value != "SuperAdmin":
            company_id = user.company_id
        
        if company_id is not None:
            filters.append("RFIDCardCompanyId = ?")
            params.append(company_id)
            
        if driver_id is not None:
            filters.append("RFIDCardDriverId = ?")
            params.append(driver_id)
            
        if enabled is not None:
            filters.append("RFIDCardEnabled = ?")
            params.append(1 if enabled else 0)
            
        if filters:
            query += f" WHERE {' AND '.join(filters)}"
            
        query += " ORDER BY RFIDCardId"
        
        rfid_cards = execute_query(query, tuple(params) if params else None)
        return rfid_cards
    except Exception as e:
        logger.error(f"Error getting RFID cards: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/{rfid_card_id}", response_model=RFIDCard)
async def get_rfid_card(
    rfid_card_id: int,
    user: UserInToken = Depends(get_current_user)
):
    """
    Get details of a specific RFID card by ID.
    
    - SuperAdmin: Can see any RFID card
    - Admin: Can only see RFID cards from their company
    - Driver: Can only see their own RFID cards
    """
    try:
        rfid_card = execute_query(
            "SELECT * FROM RFIDCards WHERE RFIDCardId = ?",
            (rfid_card_id,)
        )
        
        if not rfid_card:
            raise HTTPException(
                status_code=404,
                detail=f"RFID card with ID {rfid_card_id} not found"
            )
            
        # Check access permissions
        if user.role.value == "Driver":
            if rfid_card[0]["RFIDCardDriverId"] != user.driver_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only view your own RFID cards"
                )
        elif user.role.value == "Admin":
            if rfid_card[0]["RFIDCardCompanyId"] != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only view RFID cards from your company"
                )
        
        return rfid_card[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting RFID card {rfid_card_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.post("/", response_model=RFIDCard, status_code=201)
async def create_rfid_card(
    rfid_card: RFIDCardCreate,
    user: UserInToken = Depends(require_admin_or_higher)
):
    """
    Create a new RFID card.
    
    - SuperAdmin: Can create RFID cards for any company
    - Admin: Can only create RFID cards for their company
    - Driver: Not allowed to access this endpoint
    """
    try:
        # Validate company access
        if user.role.value != "SuperAdmin":
            if rfid_card.RFIDCardCompanyId != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only create RFID cards for your own company"
                )
        
        # Check if company exists
        company = execute_query(
            "SELECT 1 FROM Companies WHERE CompanyId = ?",
            (rfid_card.RFIDCardCompanyId,)
        )
        if not company:
            raise HTTPException(
                status_code=404,
                detail=f"Company with ID {rfid_card.RFIDCardCompanyId} not found"
            )
            
        # Check if driver exists and belongs to company
        driver = execute_query(
            "SELECT 1 FROM Drivers WHERE DriverId = ? AND DriverCompanyId = ?",
            (rfid_card.RFIDCardDriverId, rfid_card.RFIDCardCompanyId)
        )
        if not driver:
            raise HTTPException(
                status_code=404,
                detail=f"Driver with ID {rfid_card.RFIDCardDriverId} not found or does not belong to company {rfid_card.RFIDCardCompanyId}"
            )
            
        # Check if RFID card already exists
        existing_rfid_card = execute_query(
            "SELECT 1 FROM RFIDCards WHERE RFIDCardId = ?",
            (rfid_card.RFIDCardId,)
        )
        if existing_rfid_card:
            raise HTTPException(
                status_code=409,
                detail=f"RFID card with ID {rfid_card.RFIDCardId} already exists"
            )
            
        # Insert RFID card
        now = datetime.now().isoformat()
        execute_insert(
            """
            INSERT INTO RFIDCards (
                RFIDCardId, RFIDCardCompanyId, RFIDCardDriverId,
                RFIDCardNameOn, RFIDCardNumberOn, RFIDCardEnabled, RFIDCardExpiration,
                RFIDCardCreated, RFIDCardUpdated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rfid_card.RFIDCardId,
                rfid_card.RFIDCardCompanyId,
                rfid_card.RFIDCardDriverId,
                rfid_card.RFIDCardNameOn,
                rfid_card.RFIDCardNumberOn,
                1 if rfid_card.RFIDCardEnabled else 0,
                rfid_card.RFIDCardExpiration.isoformat() if rfid_card.RFIDCardExpiration else None,
                now,
                now
            )
        )
        
        # Return created RFID card
        created_rfid_card = execute_query(
            "SELECT * FROM RFIDCards WHERE RFIDCardId = ?",
            (rfid_card.RFIDCardId,)
        )
        
        logger.info(f"✅ RFID card created: {rfid_card.RFIDCardNumberOn} by {user.email}")
        return created_rfid_card[0]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating RFID card: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.put("/{rfid_card_id}", response_model=RFIDCard)
async def update_rfid_card(
    rfid_card_id: int,
    rfid_card_update: RFIDCardUpdate,
    user: UserInToken = Depends(require_admin_or_higher)
):
    """
    Update an RFID card.
    
    - SuperAdmin: Can update any RFID card
    - Admin: Can only update RFID cards from their company
    - Driver: Not allowed to access this endpoint
    """
    try:
        # Get current RFID card
        current_rfid_card = execute_query(
            "SELECT * FROM RFIDCards WHERE RFIDCardId = ?",
            (rfid_card_id,)
        )
        
        if not current_rfid_card:
            raise HTTPException(
                status_code=404,
                detail=f"RFID card with ID {rfid_card_id} not found"
            )
            
        # Check company access
        if user.role.value != "SuperAdmin":
            if current_rfid_card[0]["RFIDCardCompanyId"] != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only update RFID cards from your company"
                )
            
            # Prevent changing company for non-superadmins
            if rfid_card_update.company_id and rfid_card_update.company_id != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You cannot change an RFID card's company"
                )
            
            # Validate driver belongs to company if changing
            if rfid_card_update.driver_id:
                driver = execute_query(
                    "SELECT 1 FROM Drivers WHERE DriverId = ? AND DriverCompanyId = ?",
                    (rfid_card_update.driver_id, user.company_id)
                )
                if not driver:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Driver with ID {rfid_card_update.driver_id} not found or does not belong to your company"
                    )
        
        # Update RFID card
        now = datetime.now().isoformat()
        execute_update(
            """
            UPDATE RFIDCards SET
                RFIDCardCompanyId = ?,
                RFIDCardDriverId = ?,
                RFIDCardNumber = ?,
                RFIDCardEnabled = ?,
                RFIDCardExpiration = ?,
                RFIDCardUpdated = ?
            WHERE RFIDCardId = ?
            """,
            (
                rfid_card_update.company_id or current_rfid_card[0]["RFIDCardCompanyId"],
                rfid_card_update.driver_id or current_rfid_card[0]["RFIDCardDriverId"],
                rfid_card_update.card_number or current_rfid_card[0]["RFIDCardNumber"],
                rfid_card_update.enabled if rfid_card_update.enabled is not None else current_rfid_card[0]["RFIDCardEnabled"],
                rfid_card_update.expiration.isoformat() if rfid_card_update.expiration else current_rfid_card[0]["RFIDCardExpiration"],
                now,
                rfid_card_id
            )
        )
        
        # Return updated RFID card
        updated_rfid_card = execute_query(
            "SELECT * FROM RFIDCards WHERE RFIDCardId = ?",
            (rfid_card_id,)
        )
        
        logger.info(f"✅ RFID card updated: {rfid_card_id} by {user.email}")
        return updated_rfid_card[0]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating RFID card: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.delete("/{rfid_card_id}")
async def delete_rfid_card(
    rfid_card_id: int,
    user: UserInToken = Depends(require_admin_or_higher)
):
    """
    Delete an RFID card.
    
    - SuperAdmin: Can delete any RFID card
    - Admin: Can only delete RFID cards from their company
    - Driver: Not allowed to access this endpoint
    """
    try:
        # Get current RFID card
        current_rfid_card = execute_query(
            "SELECT * FROM RFIDCards WHERE RFIDCardId = ?",
            (rfid_card_id,)
        )
        
        if not current_rfid_card:
            raise HTTPException(
                status_code=404,
                detail=f"RFID card with ID {rfid_card_id} not found"
            )
            
        # Check company access
        if user.role.value != "SuperAdmin":
            if current_rfid_card[0]["RFIDCardCompanyId"] != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only delete RFID cards from your company"
                )
        
        # Delete RFID card
        execute_delete(
            "DELETE FROM RFIDCards WHERE RFIDCardId = ?",
            (rfid_card_id,)
        )
        
        logger.info(f"✅ RFID card deleted: {rfid_card_id} by {user.email}")
        return {"message": f"RFID card {rfid_card_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting RFID card: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# Company-specific RFID card endpoints
@company_router.get("/{company_id}/rfid_cards", response_model=List[RFIDCard])
async def get_company_rfid_cards(
    company_id: int,
    driver_id: Optional[int] = Query(None, description="Filter by driver ID"),
    enabled: Optional[bool] = Query(None, description="Filter by enabled status"),
    user: UserInToken = Depends(require_admin_or_higher)
):
    """
    Get all RFID cards for a specific company.
    
    - SuperAdmin: Can see RFID cards from any company
    - Admin: Can only see RFID cards from their company
    - Driver: Not allowed to access this endpoint
    """
    try:
        # Check company access
        check_company_access(user, company_id)

        query = "SELECT * FROM RFIDCards WHERE RFIDCardCompanyId = ?"
        params = [company_id]
        
        if driver_id is not None:
            query += " AND RFIDCardDriverId = ?"
            params.append(driver_id)
            
        if enabled is not None:
            query += " AND RFIDCardEnabled = ?"
            params.append(1 if enabled else 0)
            
        query += " ORDER BY RFIDCardId"
        
        rfid_cards = execute_query(query, tuple(params))
        return rfid_cards
        
    except Exception as e:
        logger.error(f"Error getting RFID cards for company {company_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# Driver-specific RFID card endpoints
@driver_router.get("/{driver_id}/rfid_cards", response_model=List[RFIDCard])
async def get_driver_rfid_cards(
    driver_id: int,
    company_id: int = Query(..., description="Company ID"),
    enabled: Optional[bool] = Query(None, description="Filter by enabled status"),
    user: UserInToken = Depends(get_current_user)
):
    """
    Get all RFID cards for a specific driver.
    
    - SuperAdmin: Can see any driver's RFID cards
    - Admin: Can only see RFID cards from their company's drivers
    - Driver: Can only see their own RFID cards
    """
    try:
        # Check company access
        check_company_access(user, company_id)

        # Check if driver exists and belongs to company
        driver = execute_query(
            "SELECT 1 FROM Drivers WHERE DriverId = ? AND DriverCompanyId = ?",
            (driver_id, company_id)
        )
        if not driver:
            raise HTTPException(
                status_code=404,
                detail=f"Driver with ID {driver_id} not found or does not belong to company {company_id}"
            )
            
        # Check access permissions
        if user.role.value == "Driver" and driver_id != user.driver_id:
            raise HTTPException(
                status_code=403,
                detail="You can only view your own RFID cards"
            )
            
        query = "SELECT * FROM RFIDCards WHERE RFIDCardDriverId = ? AND RFIDCardCompanyId = ?"
        params = [driver_id, company_id]
        
        if enabled is not None:
            query += " AND RFIDCardEnabled = ?"
            params.append(1 if enabled else 0)
            
        query += " ORDER BY RFIDCardId"
        
        rfid_cards = execute_query(query, tuple(params))
        return rfid_cards
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting RFID cards for driver {driver_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/company/{company_id}", response_model=List[RFIDCard])
async def get_company_rfid_cards(
    company_id: int,
    enabled: Optional[bool] = Query(None, description="Filter by enabled status"),
    user: UserInToken = Depends(require_admin_or_higher)
):
    """
    Get all RFID cards for a specific company.
    
    - SuperAdmin: Can see RFID cards from any company
    - Admin: Can only see RFID cards from their company
    - Driver: Not allowed to access this endpoint
    """
    try:
        # Check company access
        check_company_access(user, company_id)

        query = "SELECT * FROM RFIDCards WHERE RFIDCardCompanyId = ?"
        params = [company_id]
        
        if enabled is not None:
            query += " AND RFIDCardEnabled = ?"
            params.append(1 if enabled else 0)
            
        query += " ORDER BY RFIDCardNumber"
        
        cards = execute_query(query, tuple(params))
        return cards
        
    except Exception as e:
        logger.error(f"Error getting RFID cards for company {company_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/company/{company_id}/active", response_model=List[RFIDCard])
async def get_company_active_rfid_cards(
    company_id: int,
    user: UserInToken = Depends(require_admin_or_higher)
):
    """
    Get all active RFID cards for a specific company.
    
    - SuperAdmin: Can see active RFID cards from any company
    - Admin: Can only see active RFID cards from their company
    - Driver: Not allowed to access this endpoint
    """
    try:
        # Check company access
        check_company_access(user, company_id)

        query = """
            SELECT * FROM RFIDCards 
            WHERE RFIDCardCompanyId = ? AND RFIDCardEnabled = 1
            ORDER BY RFIDCardNumber
        """
        
        cards = execute_query(query, (company_id,))
        return cards
        
    except Exception as e:
        logger.error(f"Error getting active RFID cards for company {company_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")