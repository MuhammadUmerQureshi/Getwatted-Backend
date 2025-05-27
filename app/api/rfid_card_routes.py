# app/api/rfid_card_routes.py
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional
from datetime import datetime
import logging

from app.models.rfid_card import RFIDCard, RFIDCardCreate, RFIDCardUpdate
from app.db.database import execute_query, execute_insert, execute_update, execute_delete

router = APIRouter(prefix="/api/v1/rfid_cards", tags=["RFID CARDS"])
company_router = APIRouter(prefix="/api/v1/companies", tags=["COMPANIES"])
driver_router = APIRouter(prefix="/api/v1/drivers", tags=["DRIVERS"])

logger = logging.getLogger("ocpp.rfid_cards")

@router.get("/", response_model=List[RFIDCard])
async def get_rfid_cards(
    company_id: Optional[int] = Query(None, description="Filter by company ID"),
    driver_id: Optional[int] = Query(None, description="Filter by driver ID"),
    enabled: Optional[bool] = Query(None, description="Filter by enabled status")
):
    """Get a list of all RFID cards with optional filtering."""
    try:
        query = "SELECT * FROM RFIDCards"
        params = []
        
        # Build WHERE clause for filters
        filters = []
        
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
async def get_rfid_card(rfid_card_id: str):
    """Get details of a specific RFID card by ID."""
    try:
        rfid_card = execute_query(
            "SELECT * FROM RFIDCards WHERE RFIDCardId = ?", 
            (rfid_card_id,)
        )
        
        if not rfid_card:
            raise HTTPException(status_code=404, detail=f"RFID card with ID {rfid_card_id} not found")
            
        return rfid_card[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting RFID card {rfid_card_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.post("/", response_model=RFIDCard, status_code=201)
async def create_rfid_card(rfid_card: RFIDCardCreate):
    """Create a new RFID card."""
    try:
        # Check if company exists
        company = execute_query(
            "SELECT 1 FROM Companies WHERE CompanyId = ?", 
            (rfid_card.RFIDCardCompanyId,)
        )
        
        if not company:
            raise HTTPException(status_code=404, detail=f"Company with ID {rfid_card.RFIDCardCompanyId} not found")
            
        # Check if driver exists
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
            
        now = datetime.now().isoformat()
        
        # Format expiration date for database
        expiration_date = None
        if rfid_card.RFIDCardExpiration:
            expiration_date = rfid_card.RFIDCardExpiration.isoformat()
        
        # Insert new RFID card
        execute_insert(
            """
            INSERT INTO RFIDCards (
                RFIDCardId, RFIDCardCompanyId, RFIDCardDriverId, RFIDCardEnabled,
                RFIDCardNameOn, RFIDCardNumberOn, RFIDCardExpiration,
                RFIDCardCreated, RFIDCardUpdated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rfid_card.RFIDCardId,
                rfid_card.RFIDCardCompanyId,
                rfid_card.RFIDCardDriverId,
                1 if rfid_card.RFIDCardEnabled else 0,
                rfid_card.RFIDCardNameOn,
                rfid_card.RFIDCardNumberOn,
                expiration_date,
                now,
                now
            )
        )
        
        # Return the created RFID card
        return await get_rfid_card(rfid_card.RFIDCardId)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating RFID card: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.put("/{rfid_card_id}", response_model=RFIDCard)
async def update_rfid_card(rfid_card_id: str, rfid_card: RFIDCardUpdate):
    """Update an existing RFID card."""
    try:
        # Check if RFID card exists
        existing = execute_query("SELECT 1 FROM RFIDCards WHERE RFIDCardId = ?", (rfid_card_id,))
        if not existing:
            raise HTTPException(status_code=404, detail=f"RFID card with ID {rfid_card_id} not found")
        
        # Check if driver exists if provided
        if rfid_card.RFIDCardDriverId is not None:
            driver = execute_query(
                "SELECT 1 FROM Drivers WHERE DriverId = ?", 
                (rfid_card.RFIDCardDriverId,)
            )
            
            if not driver:
                raise HTTPException(status_code=404, detail=f"Driver with ID {rfid_card.RFIDCardDriverId} not found")
        
        # Build update query dynamically based on provided fields
        update_fields = []
        params = []
        
        for field, value in rfid_card.model_dump(exclude_unset=True).items():
            if value is not None:
                # Convert boolean to integer for SQLite
                if isinstance(value, bool):
                    value = 1 if value else 0
                # Convert date to string for SQLite
                if field == "RFIDCardExpiration" and value is not None:
                    value = value.isoformat()
                update_fields.append(f"{field} = ?")
                params.append(value)
                
        if not update_fields:
            # No fields to update
            return await get_rfid_card(rfid_card_id)
            
        # Add RFIDCardUpdated field
        update_fields.append("RFIDCardUpdated = ?")
        params.append(datetime.now().isoformat())
        
        # Add rfid_card_id to params
        params.append(rfid_card_id)
        
        # Execute update
        execute_update(
            f"UPDATE RFIDCards SET {', '.join(update_fields)} WHERE RFIDCardId = ?",
            tuple(params)
        )
        
        # Return updated RFID card
        return await get_rfid_card(rfid_card_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating RFID card {rfid_card_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.delete("/{rfid_card_id}", status_code=204)
async def delete_rfid_card(rfid_card_id: str):
    """Delete an RFID card."""
    try:
        # Check if RFID card exists
        existing = execute_query("SELECT 1 FROM RFIDCards WHERE RFIDCardId = ?", (rfid_card_id,))
        if not existing:
            raise HTTPException(status_code=404, detail=f"RFID card with ID {rfid_card_id} not found")
            
        # Delete RFID card
        rows_deleted = execute_delete("DELETE FROM RFIDCards WHERE RFIDCardId = ?", (rfid_card_id,))
        
        if rows_deleted == 0:
            raise HTTPException(status_code=500, detail=f"Failed to delete RFID card {rfid_card_id}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting RFID card {rfid_card_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@company_router.get("/{company_id}/rfid_cards", response_model=List[RFIDCard])
async def get_company_rfid_cards(
    company_id: int,
    enabled: Optional[bool] = Query(None, description="Filter by enabled status")
):
    """Get all RFID cards for a specific company."""
    try:
        # Check if company exists
        company = execute_query("SELECT 1 FROM Companies WHERE CompanyId = ?", (company_id,))
        if not company:
            raise HTTPException(status_code=404, detail=f"Company with ID {company_id} not found")
            
        query = "SELECT * FROM RFIDCards WHERE RFIDCardCompanyId = ?"
        params = [company_id]
        
        if enabled is not None:
            query += " AND RFIDCardEnabled = ?"
            params.append(1 if enabled else 0)
            
        query += " ORDER BY RFIDCardId"
        
        rfid_cards = execute_query(query, tuple(params))
        return rfid_cards
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting RFID cards for company {company_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@driver_router.get("/{driver_id}/rfid_cards", response_model=List[RFIDCard])
async def get_driver_rfid_cards(
    driver_id: int,
    company_id: int = Query(..., description="Company ID"),
    enabled: Optional[bool] = Query(None, description="Filter by enabled status")
):
    """Get all RFID cards for a specific driver."""
    try:
        # Check if driver exists and belongs to the company
        driver = execute_query(
            "SELECT 1 FROM Drivers WHERE DriverId = ? AND DriverCompanyId = ?", 
            (driver_id, company_id)
        )
        
        if not driver:
            raise HTTPException(
                status_code=404, 
                detail=f"Driver with ID {driver_id} not found or does not belong to company {company_id}"
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