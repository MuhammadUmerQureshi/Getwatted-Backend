# app/api/driver_routes.py
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional
from datetime import datetime
import logging

from app.models.driver import Driver, DriverCreate, DriverUpdate
from app.db.database import execute_query, execute_insert, execute_update, execute_delete

router = APIRouter(prefix="/api/v1/drivers", tags=["DRIVERS"])
company_router = APIRouter(prefix="/api/v1/companies", tags=["COMPANIES"])

logger = logging.getLogger("ocpp.drivers")

@router.get("/", response_model=List[Driver])
async def get_drivers(
    company_id: Optional[int] = Query(None, description="Filter by company ID"),
    group_id: Optional[int] = Query(None, description="Filter by driver group ID"),
    enabled: Optional[bool] = Query(None, description="Filter by enabled status")
):
    """Get a list of all drivers with optional filtering."""
    try:
        query = "SELECT * FROM Drivers"
        params = []
        
        # Build WHERE clause for filters
        filters = []
        
        if company_id is not None:
            filters.append("DriverCompanyId = ?")
            params.append(company_id)
            
        if group_id is not None:
            filters.append("DriverGroupId = ?")
            params.append(group_id)
            
        if enabled is not None:
            filters.append("DriverEnabled = ?")
            params.append(1 if enabled else 0)
            
        if filters:
            query += f" WHERE {' AND '.join(filters)}"
            
        query += " ORDER BY DriverFullName"
        
        drivers = execute_query(query, tuple(params) if params else None)
        return drivers
    except Exception as e:
        logger.error(f"Error getting drivers: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/{driver_id}", response_model=Driver)
async def get_driver(driver_id: int):
    """Get details of a specific driver by ID."""
    try:
        driver = execute_query(
            "SELECT * FROM Drivers WHERE DriverId = ?", 
            (driver_id,)
        )
        
        if not driver:
            raise HTTPException(status_code=404, detail=f"Driver with ID {driver_id} not found")
            
        return driver[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting driver {driver_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.post("/", response_model=Driver, status_code=201)
async def create_driver(driver: DriverCreate):
    """Create a new driver."""
    try:
        # Check if company exists
        company = execute_query(
            "SELECT 1 FROM Companies WHERE CompanyId = ?", 
            (driver.DriverCompanyId,)
        )
        
        if not company:
            raise HTTPException(status_code=404, detail=f"Company with ID {driver.DriverCompanyId} not found")
            
        # Check if driver group exists if provided
        if driver.DriverGroupId:
            driver_group = execute_query(
                "SELECT 1 FROM DriversGroup WHERE DriversGroupId = ?", 
                (driver.DriverGroupId,)
            )
            
            if not driver_group:
                raise HTTPException(status_code=404, detail=f"Driver group with ID {driver.DriverGroupId} not found")
        
        # Get maximum driver ID and increment by 1
        max_id_result = execute_query("SELECT MAX(DriverId) as max_id FROM Drivers")
        new_id = 1
        if max_id_result and max_id_result[0]['max_id'] is not None:
            new_id = max_id_result[0]['max_id'] + 1
            
        now = datetime.now().isoformat()
        
        # Insert new driver
        execute_insert(
            """
            INSERT INTO Drivers (
                DriverId, DriverCompanyId, DriverEnabled, DriverFullName,
                DriverEmail, DriverPhone, DriverGroupId, DriverNotifActions,
                DriverNotifPayments, DriverNotifSystem,
                DriverCreated, DriverUpdated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id,
                driver.DriverCompanyId,
                1 if driver.DriverEnabled else 0,
                driver.DriverFullName,
                driver.DriverEmail,
                driver.DriverPhone,
                driver.DriverGroupId,
                1 if driver.DriverNotifActions else 0,
                1 if driver.DriverNotifPayments else 0,
                1 if driver.DriverNotifSystem else 0,
                now,
                now
            )
        )
        
        # Return the created driver
        return await get_driver(new_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating driver: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.put("/{driver_id}", response_model=Driver)
async def update_driver(driver_id: int, driver: DriverUpdate):
    """Update an existing driver."""
    try:
        # Check if driver exists
        existing = execute_query("SELECT 1 FROM Drivers WHERE DriverId = ?", (driver_id,))
        if not existing:
            raise HTTPException(status_code=404, detail=f"Driver with ID {driver_id} not found")
        
        # Check if driver group exists if provided
        if driver.DriverGroupId:
            driver_group = execute_query(
                "SELECT 1 FROM DriversGroup WHERE DriversGroupId = ?", 
                (driver.DriverGroupId,)
            )
            
            if not driver_group:
                raise HTTPException(status_code=404, detail=f"Driver group with ID {driver.DriverGroupId} not found")
        
        # Build update query dynamically based on provided fields
        update_fields = []
        params = []
        
        for field, value in driver.model_dump(exclude_unset=True).items():
            if value is not None:
                # Convert boolean to integer for SQLite
                if isinstance(value, bool):
                    value = 1 if value else 0
                update_fields.append(f"{field} = ?")
                params.append(value)
                
        if not update_fields:
            # No fields to update
            return await get_driver(driver_id)
            
        # Add DriverUpdated field
        update_fields.append("DriverUpdated = ?")
        params.append(datetime.now().isoformat())
        
        # Add driver_id to params
        params.append(driver_id)
        
        # Execute update
        execute_update(
            f"UPDATE Drivers SET {', '.join(update_fields)} WHERE DriverId = ?",
            tuple(params)
        )
        
        # Return updated driver
        return await get_driver(driver_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating driver {driver_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.delete("/{driver_id}", status_code=204)
async def delete_driver(driver_id: int):
    """Delete a driver."""
    try:
        # Check if driver exists
        existing = execute_query("SELECT 1 FROM Drivers WHERE DriverId = ?", (driver_id,))
        if not existing:
            raise HTTPException(status_code=404, detail=f"Driver with ID {driver_id} not found")
            
        # Delete driver
        rows_deleted = execute_delete("DELETE FROM Drivers WHERE DriverId = ?", (driver_id,))
        
        if rows_deleted == 0:
            raise HTTPException(status_code=500, detail=f"Failed to delete driver {driver_id}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting driver {driver_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@company_router.get("/{company_id}/drivers", response_model=List[Driver])
async def get_company_drivers(
    company_id: int,
    enabled: Optional[bool] = Query(None, description="Filter by enabled status"),
    group_id: Optional[int] = Query(None, description="Filter by driver group ID")
):
    """Get all drivers for a specific company."""
    try:
        # Check if company exists
        company = execute_query("SELECT 1 FROM Companies WHERE CompanyId = ?", (company_id,))
        if not company:
            raise HTTPException(status_code=404, detail=f"Company with ID {company_id} not found")
            
        query = "SELECT * FROM Drivers WHERE DriverCompanyId = ?"
        params = [company_id]
        
        if enabled is not None:
            query += " AND DriverEnabled = ?"
            params.append(1 if enabled else 0)
            
        if group_id is not None:
            query += " AND DriverGroupId = ?"
            params.append(group_id)
            
        query += " ORDER BY DriverFullName"
        
        drivers = execute_query(query, tuple(params))
        return drivers
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting drivers for company {company_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")