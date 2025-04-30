from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional
from datetime import datetime
import logging

from app.models.company import Company, CompanyCreate, CompanyUpdate
from app.db.database import execute_query, execute_insert, execute_update, execute_delete

router = APIRouter(prefix="/api/v1/companies", tags=["companies"])
logger = logging.getLogger("ocpp.companies")

@router.get("/", response_model=List[Company])
async def get_companies(
    enabled: Optional[bool] = Query(None, description="Filter by enabled status")
):
    """Get a list of all companies with optional filtering."""
    try:
        query = "SELECT * FROM Companies"
        params = []
        
        if enabled is not None:
            query += " WHERE CompanyEnabled = ?"
            params.append(1 if enabled else 0)
            
        query += " ORDER BY CompanyName"
        
        companies = execute_query(query, tuple(params) if params else None)
        return companies
    except Exception as e:
        logger.error(f"Error getting companies: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/{company_id}", response_model=Company)
async def get_company(company_id: int):
    """Get details of a specific company by ID."""
    try:
        company = execute_query(
            "SELECT * FROM Companies WHERE CompanyId = ?", 
            (company_id,)
        )
        
        if not company:
            raise HTTPException(status_code=404, detail=f"Company with ID {company_id} not found")
            
        return company[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting company {company_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.post("/", response_model=Company, status_code=201)
async def create_company(company: CompanyCreate):
    """Create a new company."""
    try:
        # Get maximum company ID and increment by 1
        max_id_result = execute_query("SELECT MAX(CompanyId) as max_id FROM Companies")
        new_id = 1
        if max_id_result and max_id_result[0]['max_id'] is not None:
            new_id = max_id_result[0]['max_id'] + 1
            
        now = datetime.now().isoformat()
        
        # Insert new company
        company_id = execute_insert(
            """
            INSERT INTO Companies (
                CompanyId, CompanyName, CompanyEnabled, CompanyHomePhoto,
                CompanyBrandColour, CompanyBrandLogo, CompanyBrandFavicon,
                CompanyCreated, CompanyUpdated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id,
                company.CompanyName,
                1 if company.CompanyEnabled else 0,
                company.CompanyHomePhoto,
                company.CompanyBrandColour,
                company.CompanyBrandLogo,
                company.CompanyBrandFavicon,
                now,
                now
            )
        )
        
        # Return the created company
        return await get_company(new_id)
    except Exception as e:
        logger.error(f"Error creating company: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.put("/{company_id}", response_model=Company)
async def update_company(company_id: int, company: CompanyUpdate):
    """Update an existing company."""
    try:
        # Check if company exists
        existing = execute_query("SELECT 1 FROM Companies WHERE CompanyId = ?", (company_id,))
        if not existing:
            raise HTTPException(status_code=404, detail=f"Company with ID {company_id} not found")
        
        # Build update query dynamically based on provided fields
        update_fields = []
        params = []
        
        for field, value in company.model_dump(exclude_unset=True).items():
            if value is not None:
                # Convert boolean to integer for SQLite
                if isinstance(value, bool):
                    value = 1 if value else 0
                update_fields.append(f"{field} = ?")
                params.append(value)
                
        if not update_fields:
            # No fields to update
            return await get_company(company_id)
            
        # Add CompanyUpdated field
        update_fields.append("CompanyUpdated = ?")
        params.append(datetime.now().isoformat())
        
        # Add company_id to params
        params.append(company_id)
        
        # Execute update
        execute_update(
            f"UPDATE Companies SET {', '.join(update_fields)} WHERE CompanyId = ?",
            tuple(params)
        )
        
        # Return updated company
        return await get_company(company_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating company {company_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.delete("/{company_id}", status_code=204)
async def delete_company(company_id: int):
    """Delete a company."""
    try:
        # Check if company exists
        existing = execute_query("SELECT 1 FROM Companies WHERE CompanyId = ?", (company_id,))
        if not existing:
            raise HTTPException(status_code=404, detail=f"Company with ID {company_id} not found")
            
        # Delete company
        rows_deleted = execute_delete("DELETE FROM Companies WHERE CompanyId = ?", (company_id,))
        
        if rows_deleted == 0:
            raise HTTPException(status_code=500, detail=f"Failed to delete company {company_id}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting company {company_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")