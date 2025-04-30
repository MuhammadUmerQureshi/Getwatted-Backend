from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional
from datetime import datetime
import logging

from app.models.site import Site, SiteCreate, SiteUpdate
from app.db.database import execute_query, execute_insert, execute_update, execute_delete

router = APIRouter(prefix="/api/v1/sites", tags=["sites"])
company_router = APIRouter(prefix="/api/v1/companies", tags=["companies"])

logger = logging.getLogger("ocpp.sites")

@router.get("/", response_model=List[Site])
async def get_sites(
    company_id: Optional[int] = Query(None, description="Filter by company ID"),
    enabled: Optional[bool] = Query(None, description="Filter by enabled status")
):
    """Get a list of all sites with optional filtering."""
    try:
        query = "SELECT * FROM Sites"
        params = []
        
        # Build WHERE clause for filters
        filters = []
        
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
async def create_site(site: SiteCreate):
    """Create a new site."""
    try:
        # Check if company exists
        company = execute_query(
            "SELECT 1 FROM Companies WHERE CompanyId = ?", 
            (site.SiteCompanyID,)
        )
        
        if not company:
            raise HTTPException(status_code=404, detail=f"Company with ID {site.SiteCompanyID} not found")
            
        # Check if site group exists if provided
        if site.SiteGroupId:
            site_group = execute_query(
                "SELECT 1 FROM SitesGroup WHERE SiteGroupId = ?", 
                (site.SiteGroupId,)
            )
            
            if not site_group:
                raise HTTPException(status_code=404, detail=f"Site group with ID {site.SiteGroupId} not found")
        
        # Get maximum site ID and increment by 1
        max_id_result = execute_query("SELECT MAX(SiteId) as max_id FROM Sites")
        new_id = 1
        if max_id_result and max_id_result[0]['max_id'] is not None:
            new_id = max_id_result[0]['max_id'] + 1
            
        now = datetime.now().isoformat()
        
        # Insert new site
        site_id = execute_insert(
            """
            INSERT INTO Sites (
                SiteId, SiteCompanyID, SiteEnabled, SiteName, SiteGroupId,
                SiteAddress, SiteCity, SiteRegion, SiteCountry, SiteZipCode,
                SiteGeoCoord, SiteTaxRate, SiteContactName, SiteContactPh, 
                SiteContactEmail, SiteCreated, SiteUpdated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id,
                site.SiteCompanyID,
                1 if site.SiteEnabled else 0,
                site.SiteName,
                site.SiteGroupId,
                site.SiteAddress,
                site.SiteCity,
                site.SiteRegion,
                site.SiteCountry,
                site.SiteZipCode,
                site.SiteGeoCoord,
                site.SiteTaxRate,
                site.SiteContactName,
                site.SiteContactPh,
                site.SiteContactEmail,
                now,
                now
            )
        )
        
        # Return the created site
        return await get_site(new_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating site: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.put("/{site_id}", response_model=Site)
async def update_site(site_id: int, site: SiteUpdate):
    """Update an existing site."""
    try:
        # Check if site exists
        existing = execute_query("SELECT 1 FROM Sites WHERE SiteId = ?", (site_id,))
        if not existing:
            raise HTTPException(status_code=404, detail=f"Site with ID {site_id} not found")
        
        # Check if site group exists if provided
        if site.SiteGroupId:
            site_group = execute_query(
                "SELECT 1 FROM SitesGroup WHERE SiteGroupId = ?", 
                (site.SiteGroupId,)
            )
            
            if not site_group:
                raise HTTPException(status_code=404, detail=f"Site group with ID {site.SiteGroupId} not found")
        
        # Build update query dynamically based on provided fields
        update_fields = []
        params = []
        
        for field, value in site.model_dump(exclude_unset=True).items():
            if value is not None:
                # Convert boolean to integer for SQLite
                if isinstance(value, bool):
                    value = 1 if value else 0
                update_fields.append(f"{field} = ?")
                params.append(value)
                
        if not update_fields:
            # No fields to update
            return await get_site(site_id)
            
        # Add SiteUpdated field
        update_fields.append("SiteUpdated = ?")
        params.append(datetime.now().isoformat())
        
        # Add site_id to params
        params.append(site_id)
        
        # Execute update
        execute_update(
            f"UPDATE Sites SET {', '.join(update_fields)} WHERE SiteId = ?",
            tuple(params)
        )
        
        # Return updated site
        return await get_site(site_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating site {site_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.delete("/{site_id}", status_code=204)
async def delete_site(site_id: int):
    """Delete a site."""
    try:
        # Check if site exists
        existing = execute_query("SELECT 1 FROM Sites WHERE SiteId = ?", (site_id,))
        if not existing:
            raise HTTPException(status_code=404, detail=f"Site with ID {site_id} not found")
            
        # Delete site
        rows_deleted = execute_delete("DELETE FROM Sites WHERE SiteId = ?", (site_id,))
        
        if rows_deleted == 0:
            raise HTTPException(status_code=500, detail=f"Failed to delete site {site_id}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting site {site_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@company_router.get("/{company_id}/sites", response_model=List[Site])
async def get_company_sites(
    company_id: int,
    enabled: Optional[bool] = Query(None, description="Filter by enabled status")
):
    """Get all sites for a specific company."""
    try:
        # Check if company exists
        company = execute_query("SELECT 1 FROM Companies WHERE CompanyId = ?", (company_id,))
        if not company:
            raise HTTPException(status_code=404, detail=f"Company with ID {company_id} not found")
            
        query = "SELECT * FROM Sites WHERE SiteCompanyID = ?"
        params = [company_id]
        
        if enabled is not None:
            query += " AND SiteEnabled = ?"
            params.append(1 if enabled else 0)
            
        query += " ORDER BY SiteName"
        
        sites = execute_query(query, tuple(params))
        return sites
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting sites for company {company_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")