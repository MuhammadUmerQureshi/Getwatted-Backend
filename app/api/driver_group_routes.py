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
        logger.info(f"Getting driver groups for user {user.email} (role: {user.role.value})")
        logger.info(f"Company ID filter: {company_id}")
        
        query = "SELECT * FROM DriversGroup"
        params = []
        filters = []
        
        # Apply company filter based on role
        if user.role.value != "SuperAdmin":
            company_id = user.company_id
            logger.info(f"Non-superadmin user, using company_id from user: {company_id}")
        
        if company_id is not None:
            filters.append("DriversGroupCompanyId = ?")
            params.append(company_id)
            
        if filters:
            query += f" WHERE {' AND '.join(filters)}"
            
        query += " ORDER BY DriversGroupId"
        
        logger.info(f"Executing query: {query}")
        logger.info(f"Query params: {params}")
        
        driver_groups = execute_query(query, tuple(params) if params else None)
        
        if driver_groups is None:
            logger.error("Database query returned None")
            raise HTTPException(status_code=500, detail="Database error: Query returned None")
            
        logger.info(f"Found {len(driver_groups)} driver groups")
        
        # Process and validate each driver group
        processed_groups = []
        for group in driver_groups:
            try:
                # Convert to dict and ensure proper types
                group_data = dict(group)
                
                # Ensure DriversGroupId is an integer
                if group_data["DriversGroupId"] is None:
                    logger.error(f"Found driver group with null ID: {group_data}")
                    continue
                    
                group_data["DriversGroupId"] = int(group_data["DriversGroupId"])
                
                # Convert boolean values
                group_data["DriversGroupEnabled"] = bool(group_data["DriversGroupEnabled"])
                
                # Convert nullable fields
                if group_data["DriversGroupDiscountId"] is not None:
                    group_data["DriversGroupDiscountId"] = int(group_data["DriversGroupDiscountId"])
                if group_data["DriverTariffId"] is not None:
                    group_data["DriverTariffId"] = int(group_data["DriverTariffId"])
                if group_data["DriversGroupCompanyId"] is not None:
                    group_data["DriversGroupCompanyId"] = int(group_data["DriversGroupCompanyId"])
                
                processed_groups.append(group_data)
                
            except (ValueError, TypeError) as e:
                logger.error(f"Error processing driver group data: {str(e)}", exc_info=True)
                logger.error(f"Problematic group data: {group}")
                continue
        
        if not processed_groups:
            logger.warning("No valid driver groups found after processing")
            return []
            
        logger.info(f"Successfully processed {len(processed_groups)} driver groups")
        return processed_groups
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting driver groups: {str(e)}", exc_info=True)
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
        logger.info(f"Getting driver group {driver_group_id} for user {user.email} (role: {user.role.value})")
        
        # Validate driver_group_id
        if driver_group_id <= 0:
            raise HTTPException(
                status_code=400,
                detail="Invalid driver group ID. Must be a positive integer."
            )
        
        # Get driver group with detailed logging
        logger.info(f"Executing query for driver group {driver_group_id}")
        driver_group = execute_query(
            "SELECT * FROM DriversGroup WHERE DriversGroupId = ?",
            (driver_group_id,)
        )
        
        if not driver_group:
            logger.warning(f"Driver group {driver_group_id} not found")
            raise HTTPException(
                status_code=404,
                detail=f"Driver group with ID {driver_group_id} not found"
            )
            
        # Log the found driver group structure
        logger.info(f"Found driver group: {driver_group[0]}")
            
        # Check company access
        if user.role.value != "SuperAdmin":
            if driver_group[0]["DriversGroupCompanyId"] != user.company_id:
                logger.warning(f"User {user.email} attempted to access driver group {driver_group_id} from company {driver_group[0]['DriversGroupCompanyId']}")
                raise HTTPException(
                    status_code=403,
                    detail="You can only view driver groups from your company"
                )
        
        # Convert boolean values from SQLite (0/1) to Python bool
        driver_group_data = dict(driver_group[0])
        driver_group_data["DriversGroupEnabled"] = bool(driver_group_data["DriversGroupEnabled"])
        
        logger.info(f"Successfully retrieved driver group {driver_group_id}")
        return driver_group_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting driver group {driver_group_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}"
        )

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
        logger.info(f"Creating driver group for user {user.email} (role: {user.role.value})")
        logger.info(f"Driver group data: {driver_group.dict()}")
        
        # Validate company access
        if user.role.value != "SuperAdmin":
            if driver_group.DriversGroupCompanyId != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only create driver groups for your own company"
                )
        
        # Check if company exists
        company = execute_query(
            "SELECT 1 FROM Companies WHERE CompanyId = ?",
            (driver_group.DriversGroupCompanyId,)
        )
        if not company:
            raise HTTPException(
                status_code=404,
                detail=f"Company with ID {driver_group.DriversGroupCompanyId} not found"
            )
            
        # Check if driver group name already exists for this company
        existing_group = execute_query(
            "SELECT 1 FROM DriversGroup WHERE DriversGroupCompanyId = ? AND DriversGroupName = ?",
            (driver_group.DriversGroupCompanyId, driver_group.DriversGroupName)
        )
        if existing_group:
            raise HTTPException(
                status_code=409,
                detail=f"Driver group with name '{driver_group.DriversGroupName}' already exists for this company"
            )
            
        # Insert driver group
        now = datetime.now().isoformat()
        try:
            last_id = execute_insert(
                """
                INSERT INTO DriversGroup (
                    DriversGroupCompanyId, DriversGroupName,
                    DriversGroupEnabled, DriversGroupDiscountId,
                    DriverTariffId, DriversGroupCreated, DriversGroupUpdated
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    driver_group.DriversGroupCompanyId,
                    driver_group.DriversGroupName,
                    1 if driver_group.DriversGroupEnabled else 0,  # Convert boolean to int
                    driver_group.DriversGroupDiscountId,
                    driver_group.DriverTariffId,
                    now,
                    now
                )
            )
            
            logger.info(f"Inserted driver group with last_id: {last_id}")
            
            if last_id == -1:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to create driver group: Database returned no ID"
                )
            
            # Get the newly created driver group
            new_driver_group = execute_query(
                """
                SELECT 
                    DriversGroupId,
                    DriversGroupCompanyId,
                    DriversGroupName,
                    DriversGroupEnabled,
                    DriversGroupDiscountId,
                    DriverTariffId,
                    DriversGroupCreated,
                    DriversGroupUpdated
                FROM DriversGroup 
                WHERE DriversGroupId = ?
                """,
                (last_id,)
            )
            
            if not new_driver_group:
                logger.error(f"Failed to retrieve created driver group with ID {last_id}")
                raise HTTPException(
                    status_code=500,
                    detail="Failed to retrieve created driver group"
                )
            
            # Convert the row to a dict and ensure proper types
            driver_group_data = dict(new_driver_group[0])
            driver_group_data["DriversGroupEnabled"] = bool(driver_group_data["DriversGroupEnabled"])
            
            if driver_group_data["DriversGroupDiscountId"] is not None:
                driver_group_data["DriversGroupDiscountId"] = int(driver_group_data["DriversGroupDiscountId"])
            if driver_group_data["DriverTariffId"] is not None:
                driver_group_data["DriverTariffId"] = int(driver_group_data["DriverTariffId"])
            if driver_group_data["DriversGroupCompanyId"] is not None:
                driver_group_data["DriversGroupCompanyId"] = int(driver_group_data["DriversGroupCompanyId"])
            
            logger.info(f"✅ Driver group created successfully: {driver_group_data}")
            return driver_group_data
            
        except Exception as e:
            logger.error(f"Error during driver group creation: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create driver group: {str(e)}"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating driver group: {str(e)}", exc_info=True)
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
            "SELECT * FROM DriversGroup WHERE DriversGroupId = ?",
            (driver_group_id,)
        )
        
        if not current_driver_group:
            raise HTTPException(
                status_code=404,
                detail=f"Driver group with ID {driver_group_id} not found"
            )
            
        # Check company access
        if user.role.value != "SuperAdmin":
            if current_driver_group[0]["DriversGroupCompanyId"] != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only update driver groups from your company"
                )
        
        # Update driver group
        now = datetime.now().isoformat()
        execute_update(
            """
            UPDATE DriversGroup SET
                DriversGroupName = ?,
                DriversGroupEnabled = ?,
                DriversGroupDiscountId = ?,
                DriverTariffId = ?,
                DriversGroupUpdated = ?
            WHERE DriversGroupId = ?
            """,
            (
                driver_group_update.DriversGroupName or current_driver_group[0]["DriversGroupName"],
                1 if driver_group_update.DriversGroupEnabled else 0 if driver_group_update.DriversGroupEnabled is not None else current_driver_group[0]["DriversGroupEnabled"],
                driver_group_update.DriversGroupDiscountId if driver_group_update.DriversGroupDiscountId is not None else current_driver_group[0]["DriversGroupDiscountId"],
                driver_group_update.DriverTariffId if driver_group_update.DriverTariffId is not None else current_driver_group[0]["DriverTariffId"],
                now,
                driver_group_id
            )
        )
        
        # Return updated driver group
        updated_driver_group = execute_query(
            "SELECT * FROM DriversGroup WHERE DriversGroupId = ?",
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
            "SELECT * FROM DriversGroup WHERE DriversGroupId = ?",
            (driver_group_id,)
        )
        
        if not current_driver_group:
            raise HTTPException(
                status_code=404,
                detail=f"Driver group with ID {driver_group_id} not found"
            )
            
        # Check company access
        if user.role.value != "SuperAdmin":
            if current_driver_group[0]["DriversGroupCompanyId"] != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only delete driver groups from your company"
                )
        
        # Delete driver group
        execute_delete(
            "DELETE FROM DriversGroup WHERE DriversGroupId = ?",
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

        query = "SELECT * FROM DriversGroup WHERE DriversGroupCompanyId = ?"
        params = [company_id]
        
        if enabled is not None:
            query += " AND DriversGroupEnabled = ?"
            params.append(1 if enabled else 0)
            
        query += " ORDER BY DriversGroupName"
        
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
            "SELECT * FROM DriversGroup WHERE DriversGroupId = ?",
            (driver_group_id,)
        )
        
        if not driver_group:
            raise HTTPException(
                status_code=404,
                detail=f"Driver group with ID {driver_group_id} not found"
            )
            
        # Check company access
        if user.role.value != "SuperAdmin":
            if driver_group[0]["DriversGroupCompanyId"] != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only view drivers from your company's driver groups"
                )
        
        # Get drivers from the Drivers table
        drivers = execute_query(
            "SELECT DriverId FROM Drivers WHERE DriverGroupId = ?",
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
            "SELECT * FROM DriversGroup WHERE DriversGroupId = ?",
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
            if driver_group[0]["DriversGroupCompanyId"] != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only add drivers to your company's driver groups"
                )
            if driver[0]["DriverCompanyId"] != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only add drivers from your company"
                )
        
        # Check if driver is already in a group
        if driver[0]["DriverGroupId"] is not None:
            if driver[0]["DriverGroupId"] == driver_group_id:
                raise HTTPException(
                    status_code=409,
                    detail=f"Driver {driver_id} is already in group {driver_group_id}"
                )
            else:
                raise HTTPException(
                    status_code=409,
                    detail=f"Driver {driver_id} is already in another group"
                )
        
        # Add driver to group by updating the Drivers table
        execute_update(
            "UPDATE Drivers SET DriverGroupId = ?, DriverUpdated = ? WHERE DriverId = ?",
            (driver_group_id, datetime.now().isoformat(), driver_id)
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
            "SELECT * FROM DriversGroup WHERE DriversGroupId = ?",
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
            if driver_group[0]["DriversGroupCompanyId"] != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only remove drivers from your company's driver groups"
                )
            if driver[0]["DriverCompanyId"] != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only remove drivers from your company"
                )
        
        # Check if driver is in the specified group
        if driver[0]["DriverGroupId"] != driver_group_id:
            raise HTTPException(
                status_code=404,
                detail=f"Driver {driver_id} is not in group {driver_group_id}"
            )
        
        # Remove driver from group by updating the Drivers table
        execute_update(
            "UPDATE Drivers SET DriverGroupId = NULL, DriverUpdated = ? WHERE DriverId = ?",
            (datetime.now().isoformat(), driver_id)
        )
        
        logger.info(f"✅ Driver {driver_id} removed from group {driver_group_id} by {user.email}")
        return {"message": f"Driver {driver_id} removed from group {driver_group_id} successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing driver {driver_id} from group {driver_group_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")