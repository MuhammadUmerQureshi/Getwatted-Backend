# app/api/company_routes.py (Updated with Authentication)
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional
from datetime import datetime
import logging

from app.models.company import Company, CompanyCreate, CompanyUpdate
from app.models.auth import UserInToken
from app.db.database import execute_query, execute_insert, execute_update, execute_delete
from app.dependencies.auth import (
    require_role, 
    get_current_user
)

router = APIRouter(prefix="/api/v1/companies", tags=["COMPANIES"])
logger = logging.getLogger("ocpp.companies")

@router.get("/", response_model=List[Company])
async def get_companies(
    enabled: Optional[bool] = Query(None, description="Filter by enabled status"),
    user: UserInToken = Depends(get_current_user)
):
    """
    Get a list of companies with role-based filtering.
    
    - SuperAdmin: Can see all companies
    - Admin/Driver: Can only see their own company
    """
    try:
        if user.role.value == "SuperAdmin":
            # SuperAdmin can see all companies
            query = "SELECT * FROM Companies"
            params = []
            
            if enabled is not None:
                query += " WHERE CompanyEnabled = ?"
                params.append(1 if enabled else 0)
                
            query += " ORDER BY CompanyName"
            companies = execute_query(query, tuple(params) if params else None)
            
        else:
            # Admin/Driver can only see their own company
            if not user.company_id:
                logger.warning(f"⚠️ User {user.email} has no company_id but is not SuperAdmin")
                return []
            
            query = "SELECT * FROM Companies WHERE CompanyId = ?"
            params = [user.company_id]
            
            if enabled is not None:
                query += " AND CompanyEnabled = ?"
                params.append(1 if enabled else 0)
                
            companies = execute_query(query, tuple(params))
        
        logger.info(f"📋 User {user.email} ({user.role}) retrieved {len(companies)} companies")
        return companies
        
    except Exception as e:
        logger.error(f"Error getting companies for user {user.email}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/{company_id}", response_model=Company)
async def get_company(
    company_id: int,
    user: UserInToken = Depends(get_current_user)
):
    """
    Get details of a specific company.
    
    - SuperAdmin: Can access any company
    - Admin/Driver: Can only access their own company
    """
    try:
        # Check company access
        from app.services.auth_service import AuthService
        if not AuthService.check_company_access(user, company_id):
            logger.warning(f"⚠️ Company access denied: User {user.email} (company {user.company_id}) tried to access company {company_id}")
            raise HTTPException(
                status_code=403,
                detail=f"Access denied to company {company_id}"
            )
        
        company = execute_query(
            "SELECT * FROM Companies WHERE CompanyId = ?", 
            (company_id,)
        )
        
        if not company:
            raise HTTPException(status_code=404, detail=f"Company with ID {company_id} not found")
        
        logger.info(f"🏢 User {user.email} accessed company {company_id}")
        return company[0]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting company {company_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.post("/", response_model=Company, status_code=201)
async def create_company(
    company: CompanyCreate,
    user: UserInToken = Depends(require_role("SuperAdmin"))
):
    """
    Create a new company (SuperAdmin only).
    
    Only SuperAdmin users can create new companies.
    """
    try:
        # Check if company with the same name already exists
        existing_company = execute_query(
            "SELECT * FROM Companies WHERE CompanyName = ?", 
            (company.CompanyName,)
        )
        
        if existing_company:
            raise HTTPException(
                status_code=409, 
                detail=f"Company with name '{company.CompanyName}' already exists"
            )
        
        # Get maximum company ID and increment by 1
        max_id_result = execute_query("SELECT MAX(CompanyId) as max_id FROM Companies")
        new_id = 1
        if max_id_result and max_id_result[0]['max_id'] is not None:
            new_id = max_id_result[0]['max_id'] + 1
            
        now = datetime.now().isoformat()
        
        # Insert new company
        execute_insert(
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
        
        logger.info(f"✅ Company created: '{company.CompanyName}' (ID: {new_id}) by {user.email}")
        
        # Return the created company
        created_company = execute_query(
            "SELECT * FROM Companies WHERE CompanyId = ?", 
            (new_id,)
        )
        return created_company[0]
        
    except HTTPException:
        raise
    except Exception as e:
        # Handle database constraint violations
        if "UNIQUE constraint failed" in str(e) and "CompanyName" in str(e):
            raise HTTPException(
                status_code=409, 
                detail=f"Company with name '{company.CompanyName}' already exists"
            )
        logger.error(f"Error creating company: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.put("/{company_id}", response_model=Company)
async def update_company(
    company_id: int, 
    company: CompanyUpdate,
    user: UserInToken = Depends(require_role("Admin"))
):
    """
    Update an existing company.
    
    - SuperAdmin: Can update any company
    - Admin: Can only update their own company
    - Driver: Cannot update companies
    """
    try:
        # Check company access for Admin users
        if user.role.value == "Admin":
            from app.services.auth_service import AuthService
            if not AuthService.check_company_access(user, company_id):
                logger.warning(f"⚠️ Company access denied: User {user.email} (company {user.company_id}) tried to update company {company_id}")
                raise HTTPException(
                    status_code=403,
                    detail=f"Access denied to company {company_id}"
                )
        
        # Check if company exists
        existing = execute_query("SELECT 1 FROM Companies WHERE CompanyId = ?", (company_id,))
        if not existing:
            raise HTTPException(status_code=404, detail=f"Company with ID {company_id} not found")
        
        # Check if new company name conflicts with existing companies (excluding current one)
        if company.CompanyName is not None:
            name_conflict = execute_query(
                "SELECT 1 FROM Companies WHERE CompanyName = ? AND CompanyId != ?", 
                (company.CompanyName, company_id)
            )
            
            if name_conflict:
                raise HTTPException(
                    status_code=409, 
                    detail=f"Company with name '{company.CompanyName}' already exists"
                )
        
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
            logger.info(f"📝 No fields to update for company {company_id}")
            existing_company = execute_query(
                "SELECT * FROM Companies WHERE CompanyId = ?", 
                (company_id,)
            )
            return existing_company[0]
            
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
        
        logger.info(f"📝 Company updated: {company_id} by {user.email}")
        
        # Return updated company
        updated_company = execute_query(
            "SELECT * FROM Companies WHERE CompanyId = ?", 
            (company_id,)
        )
        return updated_company[0]
        
    except HTTPException:
        raise
    except Exception as e:
        # Handle database constraint violations
        if "UNIQUE constraint failed" in str(e) and "CompanyName" in str(e):
            raise HTTPException(
                status_code=409, 
                detail=f"Company with name '{company.CompanyName}' already exists"
            )
        logger.error(f"Error updating company {company_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.delete("/{company_id}", status_code=204)
async def delete_company(
    company_id: int,
    user: UserInToken = Depends(require_role("SuperAdmin"))
):
    """
    Delete a company (SuperAdmin only).
    
    Only SuperAdmin users can delete companies.
    This is a dangerous operation that should be used carefully.
    """
    try:
        # Check if company exists
        existing = execute_query("SELECT CompanyName FROM Companies WHERE CompanyId = ?", (company_id,))
        if not existing:
            raise HTTPException(status_code=404, detail=f"Company with ID {company_id} not found")
        
        company_name = existing[0]["CompanyName"]
        
        # Check for dependent records (optional - you might want to prevent deletion if there are sites, users, etc.)
        sites = execute_query("SELECT COUNT(*) as count FROM Sites WHERE SiteCompanyID = ?", (company_id,))
        if sites and sites[0]["count"] > 0:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot delete company {company_id} because it has {sites[0]['count']} associated sites. Delete all sites first."
            )
        
        users = execute_query("SELECT COUNT(*) as count FROM Users WHERE UserCompanyId = ?", (company_id,))
        if users and users[0]["count"] > 0:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot delete company {company_id} because it has {users[0]['count']} associated users. Delete all users first."
            )
            
        # Delete company
        rows_deleted = execute_delete("DELETE FROM Companies WHERE CompanyId = ?", (company_id,))
        
        if rows_deleted == 0:
            raise HTTPException(status_code=500, detail=f"Failed to delete company {company_id}")
        
        logger.warning(f"🗑️ Company deleted: '{company_name}' (ID: {company_id}) by {user.email}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting company {company_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# Additional endpoint for user context
@router.get("/my/info", response_model=Company)
async def get_my_company(
    user: UserInToken = Depends(require_role("Admin"))
):
    """
    Get current user's company information.
    
    Convenience endpoint for Admin/Driver users to get their company info
    without needing to know their company_id.
    """
    try:
        if not user.company_id:
            raise HTTPException(
                status_code=400, 
                detail="User has no associated company"
            )
        
        # Get the company directly since we know the user has access to their own company
        company = execute_query(
            "SELECT * FROM Companies WHERE CompanyId = ?", 
            (user.company_id,)
        )
        
        if not company:
            raise HTTPException(
                status_code=404, 
                detail=f"Company with ID {user.company_id} not found"
            )
        
        logger.info(f"🏢 User {user.email} accessed their company {user.company_id}")
        return company[0]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user's company: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# Endpoint to check company access permissions
@router.get("/{company_id}/access-check")
async def check_company_access(
    company_id: int,
    user: UserInToken = Depends(get_current_user)
):
    """
    Check if current user has access to a specific company.
    
    Utility endpoint for frontend to verify access before making requests.
    """
    try:
        from app.services.auth_service import AuthService
        
        has_access = AuthService.check_company_access(user, company_id)
        
        return {
            "company_id": company_id,
            "user_id": user.user_id,
            "user_role": user.role.value,
            "user_company_id": user.company_id,
            "has_access": has_access,
            "access_reason": "SuperAdmin" if user.role.value == "SuperAdmin" else 
                           "Own company" if has_access else "Different company"
        }
        
    except Exception as e:
        logger.error(f"Error checking company access: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error checking access: {str(e)}")