# app/api/auth_routes.py
from fastapi import APIRouter, HTTPException, Depends, status
from typing import List
import logging

from app.models.auth import LoginRequest, LoginResponse, UserInfo, UserCreate, User, UserInToken
from app.services.auth_service import AuthService
from app.dependencies.auth import require_super_admin, get_current_user
from app.db.database import execute_query, execute_insert

router = APIRouter(prefix="/api/v1/auth", tags=["AUTHENTICATION"])
logger = logging.getLogger("ocpp.auth")

@router.post("/login", response_model=LoginResponse)
async def login(credentials: LoginRequest):
    """
    Authenticate user and return JWT token.
    
    Args:
        credentials: Email and password
        
    Returns:
        JWT token and user information
    """
    try:
        # Authenticate user
        user_data = AuthService.authenticate_user(credentials.email, credentials.password)
        
        if not user_data:
            logger.warning(f"⚠️ Failed login attempt for: {credentials.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Create access token
        access_token = AuthService.create_access_token(user_data)
        
        # Create user info response
        user_info = UserInfo(
            user_id=user_data["user_id"],
            email=user_data["email"],
            role=user_data["role"],
            company_id=user_data["company_id"],
            driver_id=user_data["driver_id"],
            first_name=user_data["first_name"],
            last_name=user_data["last_name"]
        )
        
        logger.info(f"✅ User logged in: {credentials.email} ({user_data['role']})")
        
        return LoginResponse(
            access_token=access_token,
            user=user_info
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Login error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )

@router.get("/me", response_model=UserInfo)
async def get_current_user_info(user: UserInToken = Depends(get_current_user)):
    """
    Get current user information from token.
    
    Returns:
        Current user information
    """
    try:
        # Get additional user details from database
        user_details = execute_query(
            """
            SELECT u.UserFirstName, u.UserLastName, u.UserPhone, d.DriverId
            FROM Users u
            LEFT JOIN Drivers d ON u.UserId = d.DriverUserId
            WHERE u.UserId = ?
            """,
            (user.user_id,)
        )
        
        first_name = None
        last_name = None
        if user_details:
            first_name = user_details[0]["UserFirstName"]
            last_name = user_details[0]["UserLastName"]
        
        return UserInfo(
            user_id=user.user_id,
            email=user.email,
            role=user.role,
            company_id=user.company_id,
            driver_id=user.driver_id,
            first_name=first_name,
            last_name=last_name
        )
        
    except Exception as e:
        logger.error(f"❌ Error getting user info: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve user information"
        )

@router.post("/create-user", response_model=User, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    current_user: UserInToken = Depends(require_super_admin)
):
    """
    Create a new user (SuperAdmin only).
    
    Args:
        user_data: User creation data
        current_user: Current user (must be SuperAdmin)
        
    Returns:
        Created user information
    """
    try:
        # Check if user already exists
        existing_user = execute_query(
            "SELECT UserId FROM Users WHERE UserEmail = ?",
            (user_data.email,)
        )
        
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"User with email {user_data.email} already exists"
            )
        
        # Validate company exists for Admin/Driver roles
        if user_data.role != "SuperAdmin":
            if not user_data.company_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"{user_data.role} users must have a company_id"
                )
            
            company = execute_query(
                "SELECT CompanyId FROM Companies WHERE CompanyId = ?",
                (user_data.company_id,)
            )
            
            if not company:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Company with ID {user_data.company_id} not found"
                )
        
        # Get role ID
        role = execute_query(
            "SELECT UserRoleId FROM UserRoles WHERE UserRoleName = ?",
            (user_data.role.value,)
        )
        
        if not role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role: {user_data.role}"
            )
        
        role_id = role[0]["UserRoleId"]
        
        # Hash password
        password_hash = AuthService.hash_password(user_data.password)
        
        # Get next user ID
        max_id_result = execute_query("SELECT MAX(UserId) as max_id FROM Users")
        new_id = 1
        if max_id_result and max_id_result[0]['max_id'] is not None:
            new_id = max_id_result[0]['max_id'] + 1
        
        # Insert user
        from datetime import datetime
        now = datetime.now().isoformat()
        
        execute_insert(
            """
            INSERT INTO Users (
                UserId, UserRoleId, UserFirstName, UserLastName, UserEmail,
                UserPhone, UserCompanyId, UserPasswordHash, UserCreated, UserUpdated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id, role_id, user_data.first_name, user_data.last_name,
                user_data.email, user_data.phone, user_data.company_id,
                password_hash, now, now
            )
        )
        
        logger.info(f"✅ User created: {user_data.email} ({user_data.role}) by {current_user.email}")
        
        # Return created user (without password hash)
        return User(
            user_id=new_id,
            email=user_data.email,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            role=user_data.role,
            company_id=user_data.company_id,
            phone=user_data.phone,
            created_at=datetime.fromisoformat(now),
            updated_at=datetime.fromisoformat(now)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error creating user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user"
        )

@router.post("/logout")
async def logout(user: UserInToken = Depends(get_current_user)):
    """
    Logout user (client should remove token).
    
    Note: Since JWT is stateless, actual logout happens on client side
    by removing the token. This endpoint is for logging purposes.
    """
    logger.info(f"✅ User logged out: {user.email}")
    return {"message": "Successfully logged out"}

@router.get("/users", response_model=List[User])
async def list_users(current_user: UserInToken = Depends(require_super_admin)):
    """
    List all users (SuperAdmin only).
    
    Returns:
        List of all users
    """
    try:
        users = execute_query(
            """
            SELECT u.UserId, u.UserEmail, u.UserFirstName, u.UserLastName,
                   u.UserPhone, u.UserCompanyId, ur.UserRoleName,
                   u.UserCreated, u.UserUpdated
            FROM Users u
            INNER JOIN UserRoles ur ON u.UserRoleId = ur.UserRoleId
            ORDER BY u.UserCreated DESC
            """
        )
        
        return [
            User(
                user_id=user["UserId"],
                email=user["UserEmail"],
                first_name=user["UserFirstName"],
                last_name=user["UserLastName"],
                role=user["UserRoleName"],
                company_id=user["UserCompanyId"],
                phone=user["UserPhone"],
                created_at=user["UserCreated"],
                updated_at=user["UserUpdated"]
            )
            for user in users
        ]
        
    except Exception as e:
        logger.error(f"❌ Error listing users: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve users"
        )