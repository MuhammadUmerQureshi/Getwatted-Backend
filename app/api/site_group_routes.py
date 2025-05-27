from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional
from datetime import datetime
import logging

from app.models.site_group import SiteGroup, SiteGroupCreate, SiteGroupUpdate
from app.db.database import execute_query, execute_insert, execute_update, execute_delete

router = APIRouter(prefix="/api/v1/site_groups", tags=["SITE GROUPS"])
company_router = APIRouter(prefix="/api/v1/companies", tags=["COMPANIES"])

logger = logging.getLogger("ocpp.site_groups")

@router.get("/", response_model=List[SiteGroup])
async def get_site_groups(
    company_id: Optional[int] = Query(None, description="Filter by company ID"),
    enabled: Optional[bool] = Query(None, description="Filter by enabled status")
):
    """Get a list of all site groups with optional filtering."""
    try:
        query = "SELECT * FROM SitesGroup"
        params = []
        
        # Build WHERE clause for filters
        filters = []
        
        if company_id is not None:
            filters.append("SiteCompanyId = ?")
            params.append(company_id)
            
        if enabled is not None:
            filters.append("SiteGroupEnabled = ?")
            params.append(1 if enabled else 0)
            
        if filters:
            query += f" WHERE {' AND '.join(filters)}"
            
        query += " ORDER BY SiteGroupName"
        
        site_groups = execute_query(query, tuple(params) if params else None)
        return site_groups
    except Exception as e:
        logger.error(f"Error getting site groups: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/{site_group_id}", response_model=SiteGroup)
async def get_site_group(site_group_id: int):
    """Get details of a specific site group by ID."""
    try:
        site_group = execute_query(
            "SELECT * FROM SitesGroup WHERE SiteGroupId = ?", 
            (site_group_id,)
        )
        
        if not site_group:
            raise HTTPException(status_code=404, detail=f"Site group with ID {site_group_id} not found")
            
        return site_group[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting site group {site_group_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.post("/", response_model=SiteGroup, status_code=201)
async def create_site_group(site_group: SiteGroupCreate):
    """Create a new site group."""
    try:
        # Check if company exists
        company = execute_query(
            "SELECT 1 FROM Companies WHERE CompanyId = ?", 
            (site_group.SiteCompanyId,)
        )
        
        if not company:
            raise HTTPException(status_code=404, detail=f"Company with ID {site_group.SiteCompanyId} not found")
        
        # Get maximum site group ID and increment by 1
        max_id_result = execute_query("SELECT MAX(SiteGroupId) as max_id FROM SitesGroup")
        new_id = 1
        if max_id_result and max_id_result[0]['max_id'] is not None:
            new_id = max_id_result[0]['max_id'] + 1
            
        now = datetime.now().isoformat()
        
        # Insert new site group
        site_group_id = execute_insert(
            """
            INSERT INTO SitesGroup (
                SiteGroupId, SiteCompanyId, SiteGroupName, SiteGroupEnabled,
                SiteGroupCreated, SiteGroupUpdated
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                new_id,
                site_group.SiteCompanyId,
                site_group.SiteGroupName,
                1 if site_group.SiteGroupEnabled else 0,
                now,
                now
            )
        )
        
        # Return the created site group
        return await get_site_group(new_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating site group: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.put("/{site_group_id}", response_model=SiteGroup)
async def update_site_group(site_group_id: int, site_group: SiteGroupUpdate):
    """Update an existing site group."""
    try:
        # Check if site group exists
        existing = execute_query("SELECT 1 FROM SitesGroup WHERE SiteGroupId = ?", (site_group_id,))
        if not existing:
            raise HTTPException(status_code=404, detail=f"Site group with ID {site_group_id} not found")
        
        # Build update query dynamically based on provided fields
        update_fields = []
        params = []
        
        for field, value in site_group.model_dump(exclude_unset=True).items():
            if value is not None:
                # Convert boolean to integer for SQLite
                if isinstance(value, bool):
                    value = 1 if value else 0
                update_fields.append(f"{field} = ?")
                params.append(value)
                
        if not update_fields:
            # No fields to update
            return await get_site_group(site_group_id)
            
        # Add SiteGroupUpdated field
        update_fields.append("SiteGroupUpdated = ?")
        params.append(datetime.now().isoformat())
        
        # Add site_group_id to params
        params.append(site_group_id)
        
        # Execute update
        execute_update(
            f"UPDATE SitesGroup SET {', '.join(update_fields)} WHERE SiteGroupId = ?",
            tuple(params)
        )
        
        # Return updated site group
        return await get_site_group(site_group_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating site group {site_group_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.delete("/{site_group_id}", status_code=204)
async def delete_site_group(site_group_id: int):
    """Delete a site group."""
    try:
        # Check if site group exists
        existing = execute_query("SELECT 1 FROM SitesGroup WHERE SiteGroupId = ?", (site_group_id,))
        if not existing:
            raise HTTPException(status_code=404, detail=f"Site group with ID {site_group_id} not found")
        
        # Check if site group is being referenced by any sites
        referenced = execute_query(
            "SELECT 1 FROM Sites WHERE SiteGroupId = ?", 
            (site_group_id,)
        )
        
        if referenced:
            raise HTTPException(
                status_code=400, 
                detail=f"Cannot delete site group {site_group_id} because it is referenced by one or more sites"
            )
            
        # Delete site group
        rows_deleted = execute_delete("DELETE FROM SitesGroup WHERE SiteGroupId = ?", (site_group_id,))
        
        if rows_deleted == 0:
            raise HTTPException(status_code=500, detail=f"Failed to delete site group {site_group_id}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting site group {site_group_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@company_router.get("/{company_id}/site_groups", response_model=List[SiteGroup])
async def get_company_site_groups(
    company_id: int,
    enabled: Optional[bool] = Query(None, description="Filter by enabled status")
):
    """Get all site groups for a specific company."""
    try:
        # Check if company exists
        company = execute_query("SELECT 1 FROM Companies WHERE CompanyId = ?", (company_id,))
        if not company:
            raise HTTPException(status_code=404, detail=f"Company with ID {company_id} not found")
            
        query = "SELECT * FROM SitesGroup WHERE SiteCompanyId = ?"
        params = [company_id]
        
        if enabled is not None:
            query += " AND SiteGroupEnabled = ?"
            params.append(1 if enabled else 0)
            
        query += " ORDER BY SiteGroupName"
        
        site_groups = execute_query(query, tuple(params))
        return site_groups
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting site groups for company {company_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")