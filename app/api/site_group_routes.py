from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional
from datetime import datetime
import logging

from app.models.site_group import SiteGroup, SiteGroupCreate, SiteGroupUpdate
from app.models.auth import UserInToken
from app.db.database import execute_query, execute_insert, execute_update, execute_delete
from app.dependencies.auth import (
    require_role,
    get_current_user,
    require_admin_or_higher,
    check_company_access
)

router = APIRouter(prefix="/api/v1/site_groups", tags=["SITE GROUPS"])
company_router = APIRouter(prefix="/api/v1/companies", tags=["COMPANIES"])

logger = logging.getLogger("ocpp.site_groups")

@router.get("/", response_model=List[SiteGroup])
async def get_site_groups(
    company_id: Optional[int] = Query(None, description="Filter by company ID"),
    user: UserInToken = Depends(require_admin_or_higher)
):
    """
    Get a list of all site groups with optional filtering.
    
    - SuperAdmin: Can see all site groups
    - Admin: Can only see site groups from their company
    - Driver: Not allowed to access this endpoint
    """
    try:
        query = "SELECT * FROM SitesGroup"
        params = []
        filters = []
        
        # Apply company filter based on role
        if user.role.value != "SuperAdmin":
            company_id = user.company_id
        
        if company_id is not None:
            filters.append("SiteCompanyId = ?")
            params.append(company_id)
            
        if filters:
            query += f" WHERE {' AND '.join(filters)}"
            
        query += " ORDER BY SiteGroupId"
        
        site_groups = execute_query(query, tuple(params) if params else None)
        return site_groups
    except Exception as e:
        logger.error(f"Error getting site groups: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/{site_group_id}", response_model=SiteGroup)
async def get_site_group(
    site_group_id: int,
    user: UserInToken = Depends(require_admin_or_higher)
):
    """
    Get details of a specific site group by ID.
    
    - SuperAdmin: Can see any site group
    - Admin: Can only see site groups from their company
    - Driver: Not allowed to access this endpoint
    """
    try:
        site_group = execute_query(
            "SELECT * FROM SitesGroup WHERE SiteGroupId = ?",
            (site_group_id,)
        )
        
        if not site_group:
            raise HTTPException(
                status_code=404,
                detail=f"Site group with ID {site_group_id} not found"
            )
            
        # Check company access
        if user.role.value != "SuperAdmin":
            if site_group[0]["SiteCompanyId"] != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only view site groups from your company"
                )
        
        return site_group[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting site group {site_group_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.post("/", response_model=SiteGroup, status_code=201)
async def create_site_group(
    site_group: SiteGroupCreate,
    user: UserInToken = Depends(require_admin_or_higher)
):
    """
    Create a new site group.
    
    - SuperAdmin: Can create site groups for any company
    - Admin: Can only create site groups for their company
    - Driver: Not allowed to access this endpoint
    """
    try:
        # Validate company access
        if user.role.value != "SuperAdmin":
            if site_group.SiteCompanyId != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only create site groups for your own company"
                )
        
        # Check if company exists
        company = execute_query(
            "SELECT 1 FROM Companies WHERE CompanyId = ?",
            (site_group.SiteCompanyId,)
        )
        if not company:
            raise HTTPException(
                status_code=404,
                detail=f"Company with ID {site_group.SiteCompanyId} not found"
            )
            
        # Get the next available site group ID
        max_id_result = execute_query(
            "SELECT MAX(SiteGroupId) as max_id FROM SitesGroup"
        )
        next_id = (max_id_result[0]["max_id"] or 0) + 1
            
        # Insert site group
        now = datetime.now().isoformat()
        execute_insert(
            """
            INSERT INTO SitesGroup (
                SiteGroupId, SiteCompanyId, SiteGroupName,
                SiteGroupEnabled, SiteGroupCreated, SiteGroupUpdated
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                next_id,
                site_group.SiteCompanyId,
                site_group.SiteGroupName,
                site_group.SiteGroupEnabled if hasattr(site_group, 'SiteGroupEnabled') else True,
                now,
                now
            )
        )
        
        # Return created site group
        created_site_group = execute_query(
            "SELECT * FROM SitesGroup WHERE SiteGroupId = ?",
            (next_id,)
        )
        
        logger.info(f"✅ Site group created: {site_group.SiteGroupName} by {user.email}")
        return created_site_group[0]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating site group: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.put("/{site_group_id}", response_model=SiteGroup)
async def update_site_group(
    site_group_id: int,
    site_group_update: SiteGroupUpdate,
    user: UserInToken = Depends(require_admin_or_higher)
):
    """
    Update a site group.
    
    - SuperAdmin: Can update any site group
    - Admin: Can only update site groups from their company
    - Driver: Not allowed to access this endpoint
    """
    try:
        # Get current site group
        current_site_group = execute_query(
            "SELECT * FROM SitesGroup WHERE SiteGroupId = ?",
            (site_group_id,)
        )
        
        if not current_site_group:
            raise HTTPException(
                status_code=404,
                detail=f"Site group with ID {site_group_id} not found"
            )
            
        # Check company access
        if user.role.value != "SuperAdmin":
            if current_site_group[0]["SiteCompanyId"] != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only update site groups from your company"
                )
            
            # Prevent changing company for non-superadmins
            if site_group_update.SiteCompanyId and site_group_update.SiteCompanyId != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You cannot change a site group's company"
                )
        
        # Update site group
        now = datetime.now().isoformat()
        execute_update(
            """
            UPDATE SitesGroup SET
                SiteCompanyId = ?,
                SiteGroupName = ?,
                SiteGroupEnabled = ?,
                SiteGroupUpdated = ?
            WHERE SiteGroupId = ?
            """,
            (
                site_group_update.SiteCompanyId or current_site_group[0]["SiteCompanyId"],
                site_group_update.SiteGroupName or current_site_group[0]["SiteGroupName"],
                site_group_update.SiteGroupEnabled if hasattr(site_group_update, 'SiteGroupEnabled') else current_site_group[0]["SiteGroupEnabled"],
                now,
                site_group_id
            )
        )
        
        # Return updated site group
        updated_site_group = execute_query(
            "SELECT * FROM SitesGroup WHERE SiteGroupId = ?",
            (site_group_id,)
        )
        
        logger.info(f"✅ Site group updated: {site_group_id} by {user.email}")
        return updated_site_group[0]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating site group: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.delete("/{site_group_id}")
async def delete_site_group(
    site_group_id: int,
    user: UserInToken = Depends(require_admin_or_higher)
):
    """
    Delete a site group.
    
    - SuperAdmin: Can delete any site group
    - Admin: Can only delete site groups from their company
    - Driver: Not allowed to access this endpoint
    """
    try:
        # Get current site group
        current_site_group = execute_query(
            "SELECT * FROM SitesGroup WHERE SiteGroupId = ?",
            (site_group_id,)
        )
        
        if not current_site_group:
            raise HTTPException(
                status_code=404,
                detail=f"Site group with ID {site_group_id} not found"
            )
            
        # Check company access
        if user.role.value != "SuperAdmin":
            if current_site_group[0]["SiteCompanyId"] != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only delete site groups from your company"
                )
        
        # Delete site group
        execute_delete(
            "DELETE FROM SitesGroup WHERE SiteGroupId = ?",
            (site_group_id,)
        )
        
        logger.info(f"✅ Site group deleted: {site_group_id} by {user.email}")
        return {"message": f"Site group {site_group_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting site group: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# Company-specific site group endpoints
@company_router.get("/{company_id}/site_groups", response_model=List[SiteGroup])
async def get_company_site_groups(
    company_id: int,
    user: UserInToken = Depends(require_admin_or_higher),
    _: UserInToken = Depends(check_company_access)
):
    """
    Get all site groups for a specific company.
    
    - SuperAdmin: Can see site groups from any company
    - Admin: Can only see site groups from their company
    - Driver: Not allowed to access this endpoint
    """
    try:
        query = "SELECT * FROM SitesGroup WHERE SiteCompanyId = ? ORDER BY SiteGroupId"
        site_groups = execute_query(query, (company_id,))
        return site_groups
        
    except Exception as e:
        logger.error(f"Error getting site groups for company {company_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# Site group members endpoints
@router.get("/{site_group_id}/sites", response_model=List[int])
async def get_site_group_sites(
    site_group_id: int,
    user: UserInToken = Depends(require_admin_or_higher)
):
    """
    Get all sites in a specific site group.
    
    - SuperAdmin: Can see sites from any site group
    - Admin: Can only see sites from their company's site groups
    - Driver: Not allowed to access this endpoint
    """
    try:
        # Get site group
        site_group = execute_query(
            "SELECT * FROM SitesGroup WHERE SiteGroupId = ?",
            (site_group_id,)
        )
        
        if not site_group:
            raise HTTPException(
                status_code=404,
                detail=f"Site group with ID {site_group_id} not found"
            )
            
        # Check company access
        if user.role.value != "SuperAdmin":
            if site_group[0]["SiteCompanyId"] != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only view sites from your company's site groups"
                )
        
        # Get sites
        sites = execute_query(
            "SELECT SiteId FROM Sites WHERE SiteGroupId = ?",
            (site_group_id,)
        )
        return [site["SiteId"] for site in sites]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting sites for site group {site_group_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.post("/{site_group_id}/sites/{site_id}")
async def add_site_to_group(
    site_group_id: int,
    site_id: int,
    user: UserInToken = Depends(require_admin_or_higher)
):
    """
    Add a site to a site group.
    
    - SuperAdmin: Can add any site to any group
    - Admin: Can only add sites from their company to their company's groups
    - Driver: Not allowed to access this endpoint
    """
    try:
        # Get site group
        site_group = execute_query(
            "SELECT * FROM SitesGroup WHERE SiteGroupId = ?",
            (site_group_id,)
        )
        
        if not site_group:
            raise HTTPException(
                status_code=404,
                detail=f"Site group with ID {site_group_id} not found"
            )
            
        # Get site
        site = execute_query(
            "SELECT * FROM Sites WHERE SiteId = ?",
            (site_id,)
        )
        
        if not site:
            raise HTTPException(
                status_code=404,
                detail=f"Site with ID {site_id} not found"
            )
            
        # Check company access
        if user.role.value != "SuperAdmin":
            if site_group[0]["SiteCompanyId"] != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only add sites to your company's site groups"
                )
            if site[0]["SiteCompanyId"] != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only add sites from your company"
                )
        
        # Check if site is already in group
        existing = execute_query(
            "SELECT 1 FROM Sites WHERE SiteId = ? AND SiteGroupId = ?",
            (site_id, site_group_id)
        )
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Site {site_id} is already in group {site_group_id}"
            )
        
        # Update site's group
        execute_update(
            "UPDATE Sites SET SiteGroupId = ? WHERE SiteId = ?",
            (site_group_id, site_id)
        )
        
        logger.info(f"✅ Site {site_id} added to group {site_group_id} by {user.email}")
        return {"message": f"Site {site_id} added to group {site_group_id} successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding site {site_id} to group {site_group_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.delete("/{site_group_id}/sites/{site_id}")
async def remove_site_from_group(
    site_group_id: int,
    site_id: int,
    user: UserInToken = Depends(require_admin_or_higher)
):
    """
    Remove a site from a site group.
    
    - SuperAdmin: Can remove any site from any group
    - Admin: Can only remove sites from their company's groups
    - Driver: Not allowed to access this endpoint
    """
    try:
        # Get site group
        site_group = execute_query(
            "SELECT * FROM SitesGroup WHERE SiteGroupId = ?",
            (site_group_id,)
        )
        
        if not site_group:
            raise HTTPException(
                status_code=404,
                detail=f"Site group with ID {site_group_id} not found"
            )
            
        # Get site
        site = execute_query(
            "SELECT * FROM Sites WHERE SiteId = ?",
            (site_id,)
        )
        
        if not site:
            raise HTTPException(
                status_code=404,
                detail=f"Site with ID {site_id} not found"
            )
            
        # Check company access
        if user.role.value != "SuperAdmin":
            if site_group[0]["SiteCompanyId"] != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only remove sites from your company's site groups"
                )
            if site[0]["SiteCompanyId"] != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only remove sites from your company"
                )
        
        # Remove site from group
        execute_update(
            "UPDATE Sites SET SiteGroupId = NULL WHERE SiteId = ? AND SiteGroupId = ?",
            (site_id, site_group_id)
        )
        
        logger.info(f"✅ Site {site_id} removed from group {site_group_id} by {user.email}")
        return {"message": f"Site {site_id} removed from group {site_group_id} successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing site {site_id} from group {site_group_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/company/{company_id}", response_model=List[SiteGroup])
async def get_company_site_groups(
    company_id: int,
    enabled: Optional[bool] = Query(None, description="Filter by enabled status"),
    user: UserInToken = Depends(require_admin_or_higher)
):
    """
    Get all site groups for a specific company.
    
    - SuperAdmin: Can see site groups from any company
    - Admin: Can only see site groups from their company
    - Driver: Not allowed to access this endpoint
    """
    try:
        # Check company access
        check_company_access(user, company_id)

        query = "SELECT * FROM SitesGroup WHERE SiteCompanyId = ?"
        params = [company_id]
        
        if enabled is not None:
            query += " AND SiteGroupEnabled = ?"
            params.append(1 if enabled else 0)
            
        query += " ORDER BY SiteGroupName"
        
        groups = execute_query(query, tuple(params))
        return groups
        
    except Exception as e:
        logger.error(f"Error getting site groups for company {company_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")