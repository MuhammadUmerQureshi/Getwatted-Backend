from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional
from datetime import datetime
import logging

from app.models.driver_group import DriverGroup, DriverGroupCreate, DriverGroupUpdate
from app.db.database import execute_query, execute_insert, execute_update, execute_delete

router = APIRouter(prefix="/api/v1/driver_groups", tags=["driver_groups"])
company_router = APIRouter(prefix="/api/v1/companies", tags=["companies"])

logger = logging.getLogger("ocpp.driver_groups")

@router.get("/", response_model=List[DriverGroup])
async def get_driver_groups(
    company_id: Optional[int] = Query(None, description="Filter by company ID"),
    enabled: Optional[bool] = Query(None, description="Filter by enabled status")
):
    """Get a list of all driver groups with optional filtering."""
    try:
        query = "SELECT * FROM DriversGroup"
        params = []
        
        # Build WHERE clause for filters
        filters = []
        
        if company_id is not None:
            filters.append("DriversGroupCompanyId = ?")
            params.append(company_id)
            
        if enabled is not None:
            filters.append("DriversGroupEnabled = ?")
            params.append(1 if enabled else 0)
            
        if filters:
            query += f" WHERE {' AND '.join(filters)}"
            
        query += " ORDER BY DriversGroupName"
        
        driver_groups = execute_query(query, tuple(params) if params else None)
        return driver_groups
    except Exception as e:
        logger.error(f"Error getting driver groups: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/{driver_group_id}", response_model=DriverGroup)
async def get_driver_group(driver_group_id: int):
    """Get details of a specific driver group by ID."""
    try:
        driver_group = execute_query(
            "SELECT * FROM DriversGroup WHERE DriversGroupId = ?", 
            (driver_group_id,)
        )
        
        if not driver_group:
            raise HTTPException(status_code=404, detail=f"Driver group with ID {driver_group_id} not found")
            
        return driver_group[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting driver group {driver_group_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.post("/", response_model=DriverGroup, status_code=201)
async def create_driver_group(driver_group: DriverGroupCreate):
    """Create a new driver group."""
    try:
        # Check if company exists
        company = execute_query(
            "SELECT 1 FROM Companies WHERE CompanyId = ?", 
            (driver_group.DriversGroupCompanyId,)
        )
        
        if not company:
            raise HTTPException(status_code=404, detail=f"Company with ID {driver_group.DriversGroupCompanyId} not found")
            
        # Check if discount exists if provided
        if driver_group.DriversGroupDiscountId:
            discount = execute_query(
                "SELECT 1 FROM Discounts WHERE DiscountId = ?", 
                (driver_group.DriversGroupDiscountId,)
            )
            
            if not discount:
                raise HTTPException(status_code=404, detail=f"Discount with ID {driver_group.DriversGroupDiscountId} not found")
        
        # Get maximum driver group ID and increment by 1
        max_id_result = execute_query("SELECT MAX(DriversGroupId) as max_id FROM DriversGroup")
        new_id = 1
        if max_id_result and max_id_result[0]['max_id'] is not None:
            new_id = max_id_result[0]['max_id'] + 1
            
        now = datetime.now().isoformat()
        
        # Insert new driver group
        driver_group_id = execute_insert(
            """
            INSERT INTO DriversGroup (
                DriversGroupId, DriversGroupCompanyId, DriversGroupName, DriversGroupEnabled,
                DriversGroupDiscountId, DriversGroupCreated, DriversGroupUpdated
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id,
                driver_group.DriversGroupCompanyId,
                driver_group.DriversGroupName,
                1 if driver_group.DriversGroupEnabled else 0,
                driver_group.DriversGroupDiscountId,
                now,
                now
            )
        )
        
        # Return the created driver group
        return await get_driver_group(new_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating driver group: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.put("/{driver_group_id}", response_model=DriverGroup)
async def update_driver_group(driver_group_id: int, driver_group: DriverGroupUpdate):
    """Update an existing driver group."""
    try:
        # Check if driver group exists
        existing = execute_query("SELECT 1 FROM DriversGroup WHERE DriversGroupId = ?", (driver_group_id,))
        if not existing:
            raise HTTPException(status_code=404, detail=f"Driver group with ID {driver_group_id} not found")
            
        # Check if discount exists if provided
        if driver_group.DriversGroupDiscountId:
            discount = execute_query(
                "SELECT 1 FROM Discounts WHERE DiscountId = ?", 
                (driver_group.DriversGroupDiscountId,)
            )
            
            if not discount:
                raise HTTPException(status_code=404, detail=f"Discount with ID {driver_group.DriversGroupDiscountId} not found")
        
        # Build update query dynamically based on provided fields
        update_fields = []
        params = []
        
        for field, value in driver_group.model_dump(exclude_unset=True).items():
            if value is not None:
                # Convert boolean to integer for SQLite
                if isinstance(value, bool):
                    value = 1 if value else 0
                update_fields.append(f"{field} = ?")
                params.append(value)
                
        if not update_fields:
            # No fields to update
            return await get_driver_group(driver_group_id)
            
        # Add DriversGroupUpdated field
        update_fields.append("DriversGroupUpdated = ?")
        params.append(datetime.now().isoformat())
        
        # Add driver_group_id to params
        params.append(driver_group_id)
        
        # Execute update
        execute_update(
            f"UPDATE DriversGroup SET {', '.join(update_fields)} WHERE DriversGroupId = ?",
            tuple(params)
        )
        
        # Return updated driver group
        return await get_driver_group(driver_group_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating driver group {driver_group_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.delete("/{driver_group_id}", status_code=204)
async def delete_driver_group(driver_group_id: int):
    """Delete a driver group."""
    try:
        # Check if driver group exists
        existing = execute_query("SELECT 1 FROM DriversGroup WHERE DriversGroupId = ?", (driver_group_id,))
        if not existing:
            raise HTTPException(status_code=404, detail=f"Driver group with ID {driver_group_id} not found")
        
        # Check if driver group is being referenced by any drivers
        referenced = execute_query(
            "SELECT 1 FROM Drivers WHERE DriverGroupId = ?", 
            (driver_group_id,)
        )
        
        if referenced:
            raise HTTPException(
                status_code=400, 
                detail=f"Cannot delete driver group {driver_group_id} because it is referenced by one or more drivers"
            )
            
        # Delete driver group
        rows_deleted = execute_delete("DELETE FROM DriversGroup WHERE DriversGroupId = ?", (driver_group_id,))
        
        if rows_deleted == 0:
            raise HTTPException(status_code=500, detail=f"Failed to delete driver group {driver_group_id}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting driver group {driver_group_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@company_router.get("/{company_id}/driver_groups", response_model=List[DriverGroup])
async def get_company_driver_groups(
    company_id: int,
    enabled: Optional[bool] = Query(None, description="Filter by enabled status")
):
    """Get all driver groups for a specific company."""
    try:
        # Check if company exists
        company = execute_query("SELECT 1 FROM Companies WHERE CompanyId = ?", (company_id,))
        if not company:
            raise HTTPException(status_code=404, detail=f"Company with ID {company_id} not found")
            
        query = "SELECT * FROM DriversGroup WHERE DriversGroupCompanyId = ?"
        params = [company_id]
        
        if enabled is not None:
            query += " AND DriversGroupEnabled = ?"
            params.append(1 if enabled else 0)
            
        query += " ORDER BY DriversGroupName"
        
        driver_groups = execute_query(query, tuple(params))
        return driver_groups
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting driver groups for company {company_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/{driver_group_id}/drivers", response_model=List)
async def get_driver_group_drivers(
    driver_group_id: int,
    enabled: Optional[bool] = Query(None, description="Filter by enabled status")
):
    """Get all drivers in a specific driver group."""
    try:
        # Check if driver group exists
        driver_group = execute_query("SELECT 1 FROM DriversGroup WHERE DriversGroupId = ?", (driver_group_id,))
        if not driver_group:
            raise HTTPException(status_code=404, detail=f"Driver group with ID {driver_group_id} not found")
            
        query = "SELECT * FROM Drivers WHERE DriverGroupId = ?"
        params = [driver_group_id]
        
        if enabled is not None:
            query += " AND DriverEnabled = ?"
            params.append(1 if enabled else 0)
            
        query += " ORDER BY DriverFullName"
        
        drivers = execute_query(query, tuple(params))
        return drivers
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting drivers for driver group {driver_group_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")