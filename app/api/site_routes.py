from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional
from datetime import datetime
import logging

from app.models.site import Site, SiteCreate, SiteUpdate
from app.models.auth import UserInToken
from app.db.database import execute_query, execute_insert, execute_update, execute_delete
from app.dependencies.auth import (
    require_role,
    get_current_user,
    require_admin_or_higher,
    check_company_access
)

router = APIRouter(prefix="/api/v1/sites", tags=["SITES"])
company_router = APIRouter(prefix="/api/v1/companies", tags=["COMPANIES"])

logger = logging.getLogger("ocpp.sites")

@router.get("/", response_model=List[Site])
async def get_sites(
    company_id: Optional[int] = Query(None, description="Filter by company ID"),
    enabled: Optional[bool] = Query(None, description="Filter by enabled status"),
    user: UserInToken = Depends(require_admin_or_higher)
):
    """
    Get a list of all sites with optional filtering.
    
    - SuperAdmin: Can see all sites
    - Admin: Can only see sites from their company
    - Driver: Not allowed to access this endpoint
    """
    try:
        query = "SELECT * FROM Sites"
        params = []
        filters = []
        
        # Apply company filter based on role
        if user.role.value != "SuperAdmin":
            company_id = user.company_id
        
        if company_id is not None:
            filters.append("SiteCompanyID = ?")
            params.append(company_id)
            
        if enabled is not None:
            filters.append("SiteEnabled = ?")
            params.append(1 if enabled else 0)
            
        if filters:
            query += f" WHERE {' AND '.join(filters)}"
            
        query += " ORDER BY SiteName"
        
        sites = execute_query(query, tuple(params) if params else None)
        return sites
    except Exception as e:
        logger.error(f"Error getting sites: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/{site_id}", response_model=Site)
async def get_site(site_id: int):
    """Get details of a specific site by ID."""
    try:
        site = execute_query(
            "SELECT * FROM Sites WHERE SiteId = ?", 
            (site_id,)
        )
        
        if not site:
            raise HTTPException(status_code=404, detail=f"Site with ID {site_id} not found")
            
        return site[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting site {site_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.post("/", response_model=Site, status_code=201)
async def create_site(
    site: SiteCreate,
    user: UserInToken = Depends(require_admin_or_higher)
):
    """
    Create a new site.
    
    - SuperAdmin: Can create sites for any company
    - Admin: Can only create sites for their company
    - Driver: Not allowed to access this endpoint
    """
    try:
        # Validate company access
        if user.role.value != "SuperAdmin":
            if site.company_id != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only create sites for your own company"
                )
        
        # Check if company exists
        company = execute_query(
            "SELECT 1 FROM Companies WHERE CompanyId = ?",
            (site.company_id,)
        )
        if not company:
            raise HTTPException(
                status_code=404,
                detail=f"Company with ID {site.company_id} not found"
            )
        
        # Get next site ID
        max_id = execute_query("SELECT MAX(SiteId) as max_id FROM Sites")
        new_id = 1
        if max_id and max_id[0]['max_id'] is not None:
            new_id = max_id[0]['max_id'] + 1
            
        # Insert site
        now = datetime.now().isoformat()
        execute_insert(
            """
            INSERT INTO Sites (
                SiteId, SiteCompanyID, SiteName, SiteAddress,
                SiteCity, SiteState, SiteCountry, SiteZipCode,
                SiteLatitude, SiteLongitude, SiteEnabled,
                SiteCreated, SiteUpdated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id, site.company_id, site.name, site.address,
                site.city, site.state, site.country, site.zip_code,
                site.latitude, site.longitude, 1,
                now, now
            )
        )
        
        # Return created site
        created_site = execute_query(
            "SELECT * FROM Sites WHERE SiteId = ?",
            (new_id,)
        )
        
        logger.info(f"✅ Site created: {site.name} by {user.email}")
        return created_site[0]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating site: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.put("/{site_id}", response_model=Site)
async def update_site(
    site_id: int,
    site_update: SiteUpdate,
    user: UserInToken = Depends(require_admin_or_higher)
):
    """
    Update a site.
    
    - SuperAdmin: Can update any site
    - Admin: Can only update sites from their company
    - Driver: Not allowed to access this endpoint
    """
    try:
        # Get current site
        current_site = execute_query(
            "SELECT * FROM Sites WHERE SiteId = ?",
            (site_id,)
        )
        
        if not current_site:
            raise HTTPException(
                status_code=404,
                detail=f"Site with ID {site_id} not found"
            )
            
        # Check company access
        if user.role.value != "SuperAdmin":
            if current_site[0]["SiteCompanyID"] != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only update sites from your company"
                )
            
            # Prevent changing company for non-superadmins
            if site_update.company_id and site_update.company_id != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You cannot change a site's company"
                )
        
        # Update site
        now = datetime.now().isoformat()
        execute_update(
            """
            UPDATE Sites SET
                SiteCompanyID = ?,
                SiteName = ?,
                SiteAddress = ?,
                SiteCity = ?,
                SiteState = ?,
                SiteCountry = ?,
                SiteZipCode = ?,
                SiteLatitude = ?,
                SiteLongitude = ?,
                SiteEnabled = ?,
                SiteUpdated = ?
            WHERE SiteId = ?
            """,
            (
                site_update.company_id or current_site[0]["SiteCompanyID"],
                site_update.name or current_site[0]["SiteName"],
                site_update.address or current_site[0]["SiteAddress"],
                site_update.city or current_site[0]["SiteCity"],
                site_update.state or current_site[0]["SiteState"],
                site_update.country or current_site[0]["SiteCountry"],
                site_update.zip_code or current_site[0]["SiteZipCode"],
                site_update.latitude or current_site[0]["SiteLatitude"],
                site_update.longitude or current_site[0]["SiteLongitude"],
                site_update.enabled if site_update.enabled is not None else current_site[0]["SiteEnabled"],
                now,
                site_id
            )
        )
        
        # Return updated site
        updated_site = execute_query(
            "SELECT * FROM Sites WHERE SiteId = ?",
            (site_id,)
        )
        
        logger.info(f"✅ Site updated: {site_id} by {user.email}")
        return updated_site[0]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating site: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.delete("/{site_id}")
async def delete_site(
    site_id: int,
    user: UserInToken = Depends(require_admin_or_higher)
):
    """
    Delete a site.
    
    - SuperAdmin: Can delete any site
    - Admin: Can only delete sites from their company
    - Driver: Not allowed to access this endpoint
    """
    try:
        # Get current site
        current_site = execute_query(
            "SELECT * FROM Sites WHERE SiteId = ?",
            (site_id,)
        )
        
        if not current_site:
            raise HTTPException(
                status_code=404,
                detail=f"Site with ID {site_id} not found"
            )
            
        # Check company access
        if user.role.value != "SuperAdmin":
            if current_site[0]["SiteCompanyID"] != user.company_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only delete sites from your company"
                )
        
        # Delete site
        execute_delete(
            "DELETE FROM Sites WHERE SiteId = ?",
            (site_id,)
        )
        
        logger.info(f"✅ Site deleted: {site_id} by {user.email}")
        return {"message": f"Site {site_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting site: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# Company-specific site endpoints
@company_router.get("/{company_id}/sites", response_model=List[Site])
async def get_company_sites(
    company_id: int,
    enabled: Optional[bool] = Query(None, description="Filter by enabled status"),
    user: UserInToken = Depends(require_admin_or_higher)
):
    """
    Get all sites for a specific company.
    
    - SuperAdmin: Can see sites from any company
    - Admin: Can only see sites from their company
    - Driver: Not allowed to access this endpoint
    """
    try:
        # Check company access
        check_company_access(user, company_id)

        query = "SELECT * FROM Sites WHERE SiteCompanyID = ?"
        params = [company_id]
        
        if enabled is not None:
            query += " AND SiteEnabled = ?"
            params.append(1 if enabled else 0)
            
        query += " ORDER BY SiteName"
        
        sites = execute_query(query, tuple(params))
        return sites
        
    except Exception as e:
        logger.error(f"Error getting sites for company {company_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")