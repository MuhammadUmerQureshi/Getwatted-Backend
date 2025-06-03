# app/dependencies/auth.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Callable
import logging

from app.services.auth_service import AuthService
from app.models.auth import UserInToken, UserRole

logger = logging.getLogger("ocpp.auth")

# OAuth2 scheme for token extraction
security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> UserInToken:
    """
    Dependency to get current user from JWT token.
    
    Args:
        credentials: HTTP Authorization credentials containing Bearer token
        
    Returns:
        UserInToken: Current user information
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        token = credentials.credentials
        user = AuthService.verify_token(token)
        logger.debug(f"🔍 User authenticated: {user.email} ({user.role})")
        return user
    except Exception as e:
        logger.error(f"❌ Authentication failed: {str(e)}")
        raise

def require_role(required_role: str):
    """
    Dependency factory to require specific role or higher.
    
    Args:
        required_role: Minimum required role (SuperAdmin, Admin, Driver)
        
    Returns:
        Function that validates user role
    """
    def role_checker(user: UserInToken = Depends(get_current_user)) -> UserInToken:
        if not AuthService.check_role_permission(user.role.value, required_role):
            logger.warning(f"⚠️ Access denied: User {user.email} ({user.role}) tried to access {required_role} endpoint")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {required_role} role or higher. Current role: {user.role.value}"
            )
        
        logger.debug(f"✅ Role check passed: {user.role} >= {required_role}")
        return user
    
    return role_checker

def require_company_access(company_id: int):
    """
    Dependency factory to require access to specific company.
    
    Args:
        company_id: Company ID to check access for
        
    Returns:
        Function that validates company access
    """
    def company_access_checker(user: UserInToken = Depends(get_current_user)) -> UserInToken:
        if not AuthService.check_company_access(user, company_id):
            logger.warning(f"⚠️ Company access denied: User {user.email} (company {user.company_id}) tried to access company {company_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied to company {company_id}"
            )
        
        logger.debug(f"✅ Company access granted: User {user.email} can access company {company_id}")
        return user
    
    return company_access_checker

def require_super_admin(user: UserInToken = Depends(get_current_user)) -> UserInToken:
    """
    Dependency to require SuperAdmin role.
    Convenience function for require_role("SuperAdmin").
    """
    return require_role("SuperAdmin")(user)

def require_admin_or_higher(user: UserInToken = Depends(get_current_user)) -> UserInToken:
    """
    Dependency to require Admin role or higher.
    Convenience function for require_role("Admin").
    """
    return require_role("Admin")(user)

def require_any_authenticated_user(user: UserInToken = Depends(get_current_user)) -> UserInToken:
    """
    Dependency to require any authenticated user.
    Just validates token without role checking.
    """
    return user

# Additional helper dependencies

def get_user_company_id(user: UserInToken = Depends(get_current_user)) -> Optional[int]:
    """
    Dependency to get current user's company ID.
    
    Returns:
        Company ID for the current user, None for SuperAdmin
    """
    return user.company_id

def ensure_company_admin_access(company_id: int):
    """
    Dependency factory that ensures user is Admin+ AND has access to the company.
    Combines role and company access checking.
    
    Args:
        company_id: Company ID to check access for
        
    Returns:
        Function that validates both role and company access
    """
    def admin_company_checker(
        user: UserInToken = Depends(require_role("Admin")),
        _: UserInToken = Depends(require_company_access(company_id))
    ) -> UserInToken:
        return user
    
    return admin_company_checker

def check_company_access(user: UserInToken, company_id: int) -> None:
    """
    Helper function to check if a user has access to a company.
    To be used within endpoint functions.
    
    Args:
        user: The authenticated user
        company_id: Company ID to check access for
        
    Raises:
        HTTPException: If user doesn't have access to the company
    """
    if not AuthService.check_company_access(user, company_id):
        logger.warning(f"⚠️ Company access denied: User {user.email} (company {user.company_id}) tried to access company {company_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied to company {company_id}"
        )
    logger.debug(f"✅ Company access granted: User {user.email} can access company {company_id}")