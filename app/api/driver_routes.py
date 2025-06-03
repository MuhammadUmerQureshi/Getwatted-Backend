# app/api/driver_routes.py
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional
from datetime import datetime
import logging

from app.models.driver import Driver, DriverCreate, DriverUpdate
from app.models.auth import UserInToken
from app.db.database import execute_query, execute_insert, execute_update, execute_delete
from app.dependencies.auth import (
    require_role,
    get_current_user,
    require_company_access,
    require_admin_or_higher,
    check_company_access
)

router = APIRouter(prefix="/api/v1/drivers", tags=["DRIVERS"])
company_router = APIRouter(prefix="/api/v1/companies", tags=["COMPANIES"])

logger = logging.getLogger("ocpp.drivers")

@router.get("/", response_model=List[Driver])
async def get_drivers(
    company_id: Optional[int] = Query(None, description="Filter by company ID"),
    group_id: Optional[int] = Query(None, description="Filter by driver group ID"),
    enabled: Optional[bool] = Query(None, description="Filter by enabled status"),
    user: UserInToken = Depends(require_admin_or_higher)
):
    """
    Get a list of all drivers with optional filtering.
    
    - SuperAdmin: Can see all drivers
    - Admin: Can only see drivers from their company
    - Driver: Not allowed to access this endpoint
    """
    try:
        query = "SELECT * FROM Drivers"
        params = []
        filters = []
        
        # Apply company filter based on role
        if user.role.value != "SuperAdmin":
            company_id = user.company_id
        
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
async def create_driver(
    driver: DriverCreate,
    user: UserInToken = Depends(require_admin_or_higher)
):
    """
    Create a new driver.
    
    - SuperAdmin: Can create drivers for any company
    - Admin: Can only create drivers for their company
    - Driver: Not allowed to access this endpoint
    """
    try:
        # Validate company access
        if user.role.value != "SuperAdmin":
            if driver.company_id != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only create drivers for your own company"
                )
        
        # Check if company exists
        company = execute_query(
            "SELECT 1 FROM Companies WHERE CompanyId = ?",
            (driver.company_id,)
        )
        if not company:
            raise HTTPException(
                status_code=404,
                detail=f"Company with ID {driver.company_id} not found"
            )
        
        # Get next driver ID
        max_id = execute_query("SELECT MAX(DriverId) as max_id FROM Drivers")
        new_id = 1
        if max_id and max_id[0]['max_id'] is not None:
            new_id = max_id[0]['max_id'] + 1
            
        # Insert driver
        now = datetime.now().isoformat()
        execute_insert(
            """
            INSERT INTO Drivers (
                DriverId, DriverCompanyId, DriverGroupId, DriverFullName,
                DriverEmail, DriverPhone, DriverEnabled, DriverCreated, DriverUpdated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id, driver.company_id, driver.group_id, driver.full_name,
                driver.email, driver.phone, 1, now, now
            )
        )
        
        # Return created driver
        created_driver = execute_query(
            "SELECT * FROM Drivers WHERE DriverId = ?",
            (new_id,)
        )
        
        logger.info(f"✅ Driver created: {driver.full_name} by {user.email}")
        return created_driver[0]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating driver: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.put("/{driver_id}", response_model=Driver)
async def update_driver(
    driver_id: int,
    driver_update: DriverUpdate,
    user: UserInToken = Depends(require_admin_or_higher)
):
    """
    Update a driver.
    
    - SuperAdmin: Can update any driver
    - Admin: Can only update drivers from their company
    - Driver: Not allowed to access this endpoint
    """
    try:
        # Get current driver
        current_driver = execute_query(
            "SELECT * FROM Drivers WHERE DriverId = ?",
            (driver_id,)
        )
        
        if not current_driver:
            raise HTTPException(
                status_code=404,
                detail=f"Driver with ID {driver_id} not found"
            )
            
        # Check company access
        if user.role.value != "SuperAdmin":
            if current_driver[0]["DriverCompanyId"] != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only update drivers from your company"
                )
            
            # Prevent changing company for non-superadmins
            if driver_update.company_id and driver_update.company_id != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You cannot change a driver's company"
                )
        
        # Update driver
        now = datetime.now().isoformat()
        execute_update(
            """
            UPDATE Drivers SET
                DriverCompanyId = ?,
                DriverGroupId = ?,
                DriverFullName = ?,
                DriverEmail = ?,
                DriverPhone = ?,
                DriverEnabled = ?,
                DriverUpdated = ?
            WHERE DriverId = ?
            """,
            (
                driver_update.company_id or current_driver[0]["DriverCompanyId"],
                driver_update.group_id or current_driver[0]["DriverGroupId"],
                driver_update.full_name or current_driver[0]["DriverFullName"],
                driver_update.email or current_driver[0]["DriverEmail"],
                driver_update.phone or current_driver[0]["DriverPhone"],
                driver_update.enabled if driver_update.enabled is not None else current_driver[0]["DriverEnabled"],
                now,
                driver_id
            )
        )
        
        # Return updated driver
        updated_driver = execute_query(
            "SELECT * FROM Drivers WHERE DriverId = ?",
            (driver_id,)
        )
        
        logger.info(f"✅ Driver updated: {driver_id} by {user.email}")
        return updated_driver[0]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating driver: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.delete("/{driver_id}")
async def delete_driver(
    driver_id: int,
    user: UserInToken = Depends(require_admin_or_higher)
):
    """
    Delete a driver.
    
    - SuperAdmin: Can delete any driver
    - Admin: Can only delete drivers from their company
    - Driver: Not allowed to access this endpoint
    """
    try:
        # Get current driver
        current_driver = execute_query(
            "SELECT * FROM Drivers WHERE DriverId = ?",
            (driver_id,)
        )
        
        if not current_driver:
            raise HTTPException(
                status_code=404,
                detail=f"Driver with ID {driver_id} not found"
            )
            
        # Check company access
        if user.role.value != "SuperAdmin":
            if current_driver[0]["DriverCompanyId"] != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only delete drivers from your company"
                )
        
        # Delete driver
        execute_delete(
            "DELETE FROM Drivers WHERE DriverId = ?",
            (driver_id,)
        )
        
        logger.info(f"✅ Driver deleted: {driver_id} by {user.email}")
        return {"message": f"Driver {driver_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting driver: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# Company-specific driver endpoints
@company_router.get("/{company_id}/drivers", response_model=List[Driver])
async def get_company_drivers(
    company_id: int,
    group_id: Optional[int] = Query(None, description="Filter by driver group ID"),
    enabled: Optional[bool] = Query(None, description="Filter by enabled status"),
    user: UserInToken = Depends(require_admin_or_higher)
):
    """
    Get all drivers for a specific company.
    
    - SuperAdmin: Can see drivers from any company
    - Admin: Can only see drivers from their company
    - Driver: Not allowed to access this endpoint
    """
    try:
        # Check company access
        check_company_access(user, company_id)

        query = "SELECT * FROM Drivers WHERE DriverCompanyId = ?"
        params = [company_id]
        
        if group_id is not None:
            query += " AND DriverGroupId = ?"
            params.append(group_id)
        
        if enabled is not None:
            query += " AND DriverEnabled = ?"
            params.append(1 if enabled else 0)
            
        query += " ORDER BY DriverFullName"
        
        drivers = execute_query(query, tuple(params))
        return drivers
        
    except Exception as e:
        logger.error(f"Error getting drivers for company {company_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")