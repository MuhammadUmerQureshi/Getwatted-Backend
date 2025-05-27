from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional
from datetime import datetime, time
import logging

from app.models.tariff import Tariff, TariffCreate, TariffUpdate
from app.db.database import execute_query, execute_insert, execute_update, execute_delete

router = APIRouter(prefix="/api/v1/tariffs", tags=["TARIFFS"])
company_router = APIRouter(prefix="/api/v1/companies", tags=["COMPANIES"])

logger = logging.getLogger("ocpp.tariffs")

@router.get("/", response_model=List[Tariff])
async def get_tariffs(
    company_id: Optional[int] = Query(None, description="Filter by company ID"),
    enabled: Optional[bool] = Query(None, description="Filter by enabled status"),
    tariff_type: Optional[str] = Query(None, description="Filter by tariff type")
):
    """Get a list of all tariffs with optional filtering."""
    try:
        query = "SELECT * FROM Tariffs"
        params = []
        
        # Build WHERE clause for filters
        filters = []
        
        if company_id is not None:
            filters.append("TariffsCompanyId = ?")
            params.append(company_id)
            
        if enabled is not None:
            filters.append("TariffsEnabled = ?")
            params.append(1 if enabled else 0)
            
        if tariff_type is not None:
            filters.append("TariffsType = ?")
            params.append(tariff_type)
            
        if filters:
            query += f" WHERE {' AND '.join(filters)}"
            
        query += " ORDER BY TariffsName"
        
        tariffs = execute_query(query, tuple(params) if params else None)
        return tariffs
    except Exception as e:
        logger.error(f"Error getting tariffs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/{tariff_id}", response_model=Tariff)
async def get_tariff(tariff_id: int):
    """Get details of a specific tariff by ID."""
    try:
        tariff = execute_query(
            "SELECT * FROM Tariffs WHERE TariffsId = ?", 
            (tariff_id,)
        )
        
        if not tariff:
            raise HTTPException(status_code=404, detail=f"Tariff with ID {tariff_id} not found")
            
        return tariff[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting tariff {tariff_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.post("/", response_model=Tariff, status_code=201)
async def create_tariff(tariff: TariffCreate):
    """Create a new tariff."""
    try:
        # Check if company exists
        company = execute_query(
            "SELECT 1 FROM Companies WHERE CompanyId = ?", 
            (tariff.TariffsCompanyId,)
        )
        
        if not company:
            raise HTTPException(status_code=404, detail=f"Company with ID {tariff.TariffsCompanyId} not found")
        
        # Get maximum tariff ID and increment by 1
        max_id_result = execute_query("SELECT MAX(TariffsId) as max_id FROM Tariffs")
        new_id = 1
        if max_id_result and max_id_result[0]['max_id'] is not None:
            new_id = max_id_result[0]['max_id'] + 1
            
        now = datetime.now().isoformat()
        
        # Format time fields for database
        daytime_from = tariff.TariffsDaytimeFrom.strftime('%H:%M:%S') if tariff.TariffsDaytimeFrom else None
        daytime_to = tariff.TariffsDaytimeTo.strftime('%H:%M:%S') if tariff.TariffsDaytimeTo else None
        nighttime_from = tariff.TariffsNighttimeFrom.strftime('%H:%M:%S') if tariff.TariffsNighttimeFrom else None
        nighttime_to = tariff.TariffsNighttimeTo.strftime('%H:%M:%S') if tariff.TariffsNighttimeTo else None
        
        # Insert new tariff
        tariff_id = execute_insert(
            """
            INSERT INTO Tariffs (
                TariffsId, TariffsCompanyId, TariffsEnabled, TariffsName, 
                TariffsType, TariffsPer, TariffsRateDaytime, TariffsRateNighttime,
                TariffsDaytimeFrom, TariffsDaytimeTo, TariffsNighttimeFrom, TariffsNighttimeTo,
                TariffsFixedStartFee, TariffsIdleChargingFee, TariffsIdleApplyAfter,
                TariffsCreated, TariffsUpdated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id,
                tariff.TariffsCompanyId,
                1 if tariff.TariffsEnabled else 0,
                tariff.TariffsName,
                tariff.TariffsType,
                tariff.TariffsPer,
                tariff.TariffsRateDaytime,
                tariff.TariffsRateNighttime,
                daytime_from,
                daytime_to,
                nighttime_from,
                nighttime_to,
                tariff.TariffsFixedStartFee,
                tariff.TariffsIdleChargingFee,
                tariff.TariffsIdleApplyAfter,
                now,
                now
            )
        )
        
        # Return the created tariff
        return await get_tariff(new_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating tariff: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.put("/{tariff_id}", response_model=Tariff)
async def update_tariff(tariff_id: int, tariff: TariffUpdate):
    """Update an existing tariff."""
    try:
        # Check if tariff exists
        existing = execute_query("SELECT 1 FROM Tariffs WHERE TariffsId = ?", (tariff_id,))
        if not existing:
            raise HTTPException(status_code=404, detail=f"Tariff with ID {tariff_id} not found")
        
        # Build update query dynamically based on provided fields
        update_fields = []
        params = []
        
        for field, value in tariff.model_dump(exclude_unset=True).items():
            if value is not None:
                # Convert boolean to integer for SQLite
                if isinstance(value, bool):
                    value = 1 if value else 0
                # Convert time objects to string
                elif isinstance(value, time):
                    value = value.strftime('%H:%M:%S')
                update_fields.append(f"{field} = ?")
                params.append(value)
                
        if not update_fields:
            # No fields to update
            return await get_tariff(tariff_id)
            
        # Add TariffsUpdated field
        update_fields.append("TariffsUpdated = ?")
        params.append(datetime.now().isoformat())
        
        # Add tariff_id to params
        params.append(tariff_id)
        
        # Execute update
        execute_update(
            f"UPDATE Tariffs SET {', '.join(update_fields)} WHERE TariffsId = ?",
            tuple(params)
        )
        
        # Return updated tariff
        return await get_tariff(tariff_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating tariff {tariff_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.delete("/{tariff_id}", status_code=204)
async def delete_tariff(tariff_id: int):
    """Delete a tariff."""
    try:
        # Check if tariff exists
        existing = execute_query("SELECT 1 FROM Tariffs WHERE TariffsId = ?", (tariff_id,))
        if not existing:
            raise HTTPException(status_code=404, detail=f"Tariff with ID {tariff_id} not found")
        
        # Check if tariff is being referenced by any drivers
        drivers_using_tariff = execute_query(
            "SELECT 1 FROM Drivers WHERE DriverTariffId = ?", 
            (tariff_id,)
        )
        
        if drivers_using_tariff:
            raise HTTPException(
                status_code=400, 
                detail=f"Cannot delete tariff {tariff_id} because it is associated with one or more drivers"
            )
            
        # Check if tariff is being referenced by any charge sessions
        sessions_using_tariff = execute_query(
            "SELECT 1 FROM ChargeSessions WHERE ChargerSessionPricingPlanId = ?", 
            (tariff_id,)
        )
        
        if sessions_using_tariff:
            raise HTTPException(
                status_code=400, 
                detail=f"Cannot delete tariff {tariff_id} because it is associated with one or more charge sessions"
            )
            
        # Delete tariff
        rows_deleted = execute_delete("DELETE FROM Tariffs WHERE TariffsId = ?", (tariff_id,))
        
        if rows_deleted == 0:
            raise HTTPException(status_code=500, detail=f"Failed to delete tariff {tariff_id}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting tariff {tariff_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@company_router.get("/{company_id}/tariffs", response_model=List[Tariff])
async def get_company_tariffs(
    company_id: int,
    enabled: Optional[bool] = Query(None, description="Filter by enabled status"),
    tariff_type: Optional[str] = Query(None, description="Filter by tariff type")
):
    """Get all tariffs for a specific company."""
    try:
        # Check if company exists
        company = execute_query("SELECT 1 FROM Companies WHERE CompanyId = ?", (company_id,))
        if not company:
            raise HTTPException(status_code=404, detail=f"Company with ID {company_id} not found")
            
        query = "SELECT * FROM Tariffs WHERE TariffsCompanyId = ?"
        params = [company_id]
        
        if enabled is not None:
            query += " AND TariffsEnabled = ?"
            params.append(1 if enabled else 0)
            
        if tariff_type is not None:
            query += " AND TariffsType = ?"
            params.append(tariff_type)
            
        query += " ORDER BY TariffsName"
        
        tariffs = execute_query(query, tuple(params))
        return tariffs
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting tariffs for company {company_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/{tariff_id}/drivers", response_model=List)
async def get_tariff_drivers(
    tariff_id: int,
    enabled: Optional[bool] = Query(None, description="Filter by enabled status")
):
    """Get all drivers using a specific tariff."""
    try:
        # Check if tariff exists
        tariff = execute_query("SELECT 1 FROM Tariffs WHERE TariffsId = ?", (tariff_id,))
        if not tariff:
            raise HTTPException(status_code=404, detail=f"Tariff with ID {tariff_id} not found")
            
        query = "SELECT * FROM Drivers WHERE DriverTariffId = ?"
        params = [tariff_id]
        
        if enabled is not None:
            query += " AND DriverEnabled = ?"
            params.append(1 if enabled else 0)
            
        query += " ORDER BY DriverFullName"
        
        drivers = execute_query(query, tuple(params))
        return drivers
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting drivers for tariff {tariff_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")