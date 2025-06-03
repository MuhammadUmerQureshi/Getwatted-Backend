from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional
from datetime import datetime
import logging

from app.models.driver_group import DriverGroup, DriverGroupCreate, DriverGroupUpdate
from app.models.auth import UserInToken
from app.db.database import execute_query, execute_insert, execute_update, execute_delete
from app.dependencies.auth import (
    require_role,
    get_current_user,
    require_company_access,
    require_admin_or_higher,
    check_company_access
)

router = APIRouter(prefix="/api/v1/driver_groups", tags=["DRIVER GROUPS"])
company_router = APIRouter(prefix="/api/v1/companies", tags=["COMPANIES"])

logger = logging.getLogger("ocpp.driver_groups")

@router.get("/", response_model=List[DriverGroup])
async def get_driver_groups(
    company_id: Optional[int] = Query(None, description="Filter by company ID"),
    user: UserInToken = Depends(require_admin_or_higher)
):
    """
    Get a list of all driver groups with optional filtering.
    
    - SuperAdmin: Can see all driver groups
    - Admin: Can only see driver groups from their company
    - Driver: Not allowed to access this endpoint
    """
    try:
        query = "SELECT * FROM DriverGroups"
        params = []
        filters = []
        
        # Apply company filter based on role
        if user.role.value != "SuperAdmin":
            company_id = user.company_id
        
        if company_id is not None:
            filters.append("DriverGroupCompanyId = ?")
            params.append(company_id)
            
        if filters:
            query += f" WHERE {' AND '.join(filters)}"
            
        query += " ORDER BY DriverGroupId"
        
        driver_groups = execute_query(query, tuple(params) if params else None)
        return driver_groups
    except Exception as e:
        logger.error(f"Error getting driver groups: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/{driver_group_id}", response_model=DriverGroup)
async def get_driver_group(
    driver_group_id: int,
    user: UserInToken = Depends(require_admin_or_higher)
):
    """
    Get details of a specific driver group by ID.
    
    - SuperAdmin: Can see any driver group
    - Admin: Can only see driver groups from their company
    - Driver: Not allowed to access this endpoint
    """
    try:
        driver_group = execute_query(
            "SELECT * FROM DriverGroups WHERE DriverGroupId = ?",
            (driver_group_id,)
        )
        
        if not driver_group:
            raise HTTPException(
                status_code=404,
                detail=f"Driver group with ID {driver_group_id} not found"
            )
            
        # Check company access
        if user.role.value != "SuperAdmin":
            if driver_group[0]["DriverGroupCompanyId"] != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only view driver groups from your company"
                )
        
        return driver_group[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting driver group {driver_group_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.post("/", response_model=DriverGroup, status_code=201)
async def create_driver_group(
    driver_group: DriverGroupCreate,
    user: UserInToken = Depends(require_admin_or_higher)
):
    """
    Create a new driver group.
    
    - SuperAdmin: Can create driver groups for any company
    - Admin: Can only create driver groups for their company
    - Driver: Not allowed to access this endpoint
    """
    try:
        # Validate company access
        if user.role.value != "SuperAdmin":
            if driver_group.company_id != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only create driver groups for your own company"
                )
        
        # Check if company exists
        company = execute_query(
            "SELECT 1 FROM Companies WHERE CompanyId = ?",
            (driver_group.company_id,)
        )
        if not company:
            raise HTTPException(
                status_code=404,
                detail=f"Company with ID {driver_group.company_id} not found"
            )
            
        # Check if driver group already exists
        existing_driver_group = execute_query(
            "SELECT 1 FROM DriverGroups WHERE DriverGroupId = ?",
            (driver_group.driver_group_id,)
        )
        if existing_driver_group:
            raise HTTPException(
                status_code=409,
                detail=f"Driver group with ID {driver_group.driver_group_id} already exists"
            )
            
        # Insert driver group
        now = datetime.now().isoformat()
        execute_insert(
            """
            INSERT INTO DriverGroups (
                DriverGroupId, DriverGroupCompanyId, DriverGroupName,
                DriverGroupDescription, DriverGroupCreated, DriverGroupUpdated
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                driver_group.driver_group_id,
                driver_group.company_id,
                driver_group.name,
                driver_group.description,
                now,
                now
            )
        )
        
        # Return created driver group
        created_driver_group = execute_query(
            "SELECT * FROM DriverGroups WHERE DriverGroupId = ?",
            (driver_group.driver_group_id,)
        )
        
        logger.info(f"✅ Driver group created: {driver_group.name} by {user.email}")
        return created_driver_group[0]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating driver group: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.put("/{driver_group_id}", response_model=DriverGroup)
async def update_driver_group(
    driver_group_id: int,
    driver_group_update: DriverGroupUpdate,
    user: UserInToken = Depends(require_admin_or_higher)
):
    """
    Update a driver group.
    
    - SuperAdmin: Can update any driver group
    - Admin: Can only update driver groups from their company
    - Driver: Not allowed to access this endpoint
    """
    try:
        # Get current driver group
        current_driver_group = execute_query(
            "SELECT * FROM DriverGroups WHERE DriverGroupId = ?",
            (driver_group_id,)
        )
        
        if not current_driver_group:
            raise HTTPException(
                status_code=404,
                detail=f"Driver group with ID {driver_group_id} not found"
            )
            
        # Check company access
        if user.role.value != "SuperAdmin":
            if current_driver_group[0]["DriverGroupCompanyId"] != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only update driver groups from your company"
                )
            
            # Prevent changing company for non-superadmins
            if driver_group_update.company_id and driver_group_update.company_id != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You cannot change a driver group's company"
                )
        
        # Update driver group
        now = datetime.now().isoformat()
        execute_update(
            """
            UPDATE DriverGroups SET
                DriverGroupCompanyId = ?,
                DriverGroupName = ?,
                DriverGroupDescription = ?,
                DriverGroupUpdated = ?
            WHERE DriverGroupId = ?
            """,
            (
                driver_group_update.company_id or current_driver_group[0]["DriverGroupCompanyId"],
                driver_group_update.name or current_driver_group[0]["DriverGroupName"],
                driver_group_update.description or current_driver_group[0]["DriverGroupDescription"],
                now,
                driver_group_id
            )
        )
        
        # Return updated driver group
        updated_driver_group = execute_query(
            "SELECT * FROM DriverGroups WHERE DriverGroupId = ?",
            (driver_group_id,)
        )
        
        logger.info(f"✅ Driver group updated: {driver_group_id} by {user.email}")
        return updated_driver_group[0]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating driver group: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.delete("/{driver_group_id}")
async def delete_driver_group(
    driver_group_id: int,
    user: UserInToken = Depends(require_admin_or_higher)
):
    """
    Delete a driver group.
    
    - SuperAdmin: Can delete any driver group
    - Admin: Can only delete driver groups from their company
    - Driver: Not allowed to access this endpoint
    """
    try:
        # Get current driver group
        current_driver_group = execute_query(
            "SELECT * FROM DriverGroups WHERE DriverGroupId = ?",
            (driver_group_id,)
        )
        
        if not current_driver_group:
            raise HTTPException(
                status_code=404,
                detail=f"Driver group with ID {driver_group_id} not found"
            )
            
        # Check company access
        if user.role.value != "SuperAdmin":
            if current_driver_group[0]["DriverGroupCompanyId"] != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only delete driver groups from your company"
                )
        
        # Delete driver group
        execute_delete(
            "DELETE FROM DriverGroups WHERE DriverGroupId = ?",
            (driver_group_id,)
        )
        
        logger.info(f"✅ Driver group deleted: {driver_group_id} by {user.email}")
        return {"message": f"Driver group {driver_group_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting driver group: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# Company-specific driver group endpoints
@company_router.get("/{company_id}/driver_groups", response_model=List[DriverGroup])
async def get_company_driver_groups(
    company_id: int,
    enabled: Optional[bool] = Query(None, description="Filter by enabled status"),
    user: UserInToken = Depends(require_admin_or_higher)
):
    """
    Get all driver groups for a specific company.
    
    - SuperAdmin: Can see driver groups from any company
    - Admin: Can only see driver groups from their company
    - Driver: Not allowed to access this endpoint
    """
    try:
        # Check company access
        check_company_access(user, company_id)

        query = "SELECT * FROM DriverGroups WHERE DriverGroupCompanyId = ?"
        params = [company_id]
        
        if enabled is not None:
            query += " AND DriverGroupEnabled = ?"
            params.append(1 if enabled else 0)
            
        query += " ORDER BY DriverGroupName"
        
        groups = execute_query(query, tuple(params))
        return groups
        
    except Exception as e:
        logger.error(f"Error getting driver groups for company {company_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# Driver group members endpoints
@router.get("/{driver_group_id}/drivers", response_model=List[int])
async def get_driver_group_drivers(
    driver_group_id: int,
    user: UserInToken = Depends(require_admin_or_higher)
):
    """
    Get all drivers in a specific driver group.
    
    - SuperAdmin: Can see drivers from any driver group
    - Admin: Can only see drivers from their company's driver groups
    - Driver: Not allowed to access this endpoint
    """
    try:
        # Get driver group
        driver_group = execute_query(
            "SELECT * FROM DriverGroups WHERE DriverGroupId = ?",
            (driver_group_id,)
        )
        
        if not driver_group:
            raise HTTPException(
                status_code=404,
                detail=f"Driver group with ID {driver_group_id} not found"
            )
            
        # Check company access
        if user.role.value != "SuperAdmin":
            if driver_group[0]["DriverGroupCompanyId"] != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only view drivers from your company's driver groups"
                )
        
        # Get drivers
        drivers = execute_query(
            "SELECT DriverId FROM DriverGroupMembers WHERE DriverGroupId = ?",
            (driver_group_id,)
        )
        return [driver["DriverId"] for driver in drivers]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting drivers for driver group {driver_group_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.post("/{driver_group_id}/drivers/{driver_id}")
async def add_driver_to_group(
    driver_group_id: int,
    driver_id: int,
    user: UserInToken = Depends(require_admin_or_higher)
):
    """
    Add a driver to a driver group.
    
    - SuperAdmin: Can add any driver to any group
    - Admin: Can only add drivers from their company to their company's groups
    - Driver: Not allowed to access this endpoint
    """
    try:
        # Get driver group
        driver_group = execute_query(
            "SELECT * FROM DriverGroups WHERE DriverGroupId = ?",
            (driver_group_id,)
        )
        
        if not driver_group:
            raise HTTPException(
                status_code=404,
                detail=f"Driver group with ID {driver_group_id} not found"
            )
            
        # Get driver
        driver = execute_query(
            "SELECT * FROM Drivers WHERE DriverId = ?",
            (driver_id,)
        )
        
        if not driver:
            raise HTTPException(
                status_code=404,
                detail=f"Driver with ID {driver_id} not found"
            )
            
        # Check company access
        if user.role.value != "SuperAdmin":
            if driver_group[0]["DriverGroupCompanyId"] != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only add drivers to your company's driver groups"
                )
            if driver[0]["DriverCompanyId"] != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only add drivers from your company"
                )
        
        # Check if driver is already in group
        existing = execute_query(
            "SELECT 1 FROM DriverGroupMembers WHERE DriverGroupId = ? AND DriverId = ?",
            (driver_group_id, driver_id)
        )
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Driver {driver_id} is already in group {driver_group_id}"
            )
        
        # Add driver to group
        execute_insert(
            "INSERT INTO DriverGroupMembers (DriverGroupId, DriverId) VALUES (?, ?)",
            (driver_group_id, driver_id)
        )
        
        logger.info(f"✅ Driver {driver_id} added to group {driver_group_id} by {user.email}")
        return {"message": f"Driver {driver_id} added to group {driver_group_id} successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding driver {driver_id} to group {driver_group_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.delete("/{driver_group_id}/drivers/{driver_id}")
async def remove_driver_from_group(
    driver_group_id: int,
    driver_id: int,
    user: UserInToken = Depends(require_admin_or_higher)
):
    """
    Remove a driver from a driver group.
    
    - SuperAdmin: Can remove any driver from any group
    - Admin: Can only remove drivers from their company's groups
    - Driver: Not allowed to access this endpoint
    """
    try:
        # Get driver group
        driver_group = execute_query(
            "SELECT * FROM DriverGroups WHERE DriverGroupId = ?",
            (driver_group_id,)
        )
        
        if not driver_group:
            raise HTTPException(
                status_code=404,
                detail=f"Driver group with ID {driver_group_id} not found"
            )
            
        # Get driver
        driver = execute_query(
            "SELECT * FROM Drivers WHERE DriverId = ?",
            (driver_id,)
        )
        
        if not driver:
            raise HTTPException(
                status_code=404,
                detail=f"Driver with ID {driver_id} not found"
            )
            
        # Check company access
        if user.role.value != "SuperAdmin":
            if driver_group[0]["DriverGroupCompanyId"] != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only remove drivers from your company's driver groups"
                )
            if driver[0]["DriverCompanyId"] != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only remove drivers from your company"
                )
        
        # Check if driver is in group
        existing = execute_query(
            "SELECT 1 FROM DriverGroupMembers WHERE DriverGroupId = ? AND DriverId = ?",
            (driver_group_id, driver_id)
        )
        if not existing:
            raise HTTPException(
                status_code=404,
                detail=f"Driver {driver_id} is not in group {driver_group_id}"
            )
        
        # Remove driver from group
        execute_delete(
            "DELETE FROM DriverGroupMembers WHERE DriverGroupId = ? AND DriverId = ?",
            (driver_group_id, driver_id)
        )
        
        logger.info(f"✅ Driver {driver_id} removed from group {driver_group_id} by {user.email}")
        return {"message": f"Driver {driver_id} removed from group {driver_group_id} successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing driver {driver_id} from group {driver_group_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")