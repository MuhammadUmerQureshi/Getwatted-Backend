# app/api/auth_routes.py
from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional
import logging
from datetime import datetime

from app.models.auth import LoginRequest, LoginResponse, UserInfo, UserCreate, User, UserInToken, UserUpdate
from app.services.auth_service import AuthService
from app.dependencies.auth import require_super_admin, get_current_user, require_admin_or_higher, require_any_authenticated_user, check_company_access
from app.db.database import execute_query, execute_insert, execute_delete

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
    current_user: UserInToken = Depends(require_admin_or_higher)
):
    """
    Create a new user.
    - SuperAdmin can create any type of user
    - Admin can only create Driver users for their company
    
    Args:
        user_data: User creation data
        current_user: Current user (must be Admin or SuperAdmin)
        
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
        
        # Role and company validation based on current user's role
        if current_user.role.value == "Admin":
            # Admin can only create Driver users
            if user_data.role.value != "Driver":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Admins can only create Driver users"
                )
            
            # Admin can only create users for their company
            if user_data.company_id != current_user.company_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Admins can only create users for their own company"
                )
        elif current_user.role.value == "SuperAdmin":
            # SuperAdmin can create any role except SuperAdmin
            if user_data.role.value == "SuperAdmin":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot create SuperAdmin users through this endpoint"
                )
            
            # Validate company exists for Admin/Driver roles
            if user_data.role.value != "SuperAdmin" and not user_data.company_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"{user_data.role.value} users must have a company_id"
                )
        
        # Validate company exists
        if user_data.company_id:
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
async def list_users(current_user: UserInToken = Depends(require_admin_or_higher)):
    """
    List users.
    - SuperAdmin can list all users
    - Admin can only list users from their company
    
    Returns:
        List of users
    """
    try:
        # Base query
        query = """
            SELECT u.UserId, u.UserEmail, u.UserFirstName, u.UserLastName,
                   u.UserPhone, u.UserCompanyId, ur.UserRoleName,
                   u.UserCreated, u.UserUpdated
            FROM Users u
            INNER JOIN UserRoles ur ON u.UserRoleId = ur.UserRoleId
        """
        
        # Add company filter for Admin users
        params = []
        if current_user.role.value == "Admin":
            query += " WHERE u.UserCompanyId = ?"
            params.append(current_user.company_id)
        
        query += " ORDER BY u.UserCreated DESC"
        
        users = execute_query(query, tuple(params))
        
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

@router.put("/users/{user_id}", response_model=User)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    current_user: UserInToken = Depends(require_any_authenticated_user)
):
    """
    Update user information.
    
    Args:
        user_id: ID of user to update
        user_data: Updated user information
        current_user: Current authenticated user
        
    Returns:
        Updated user information
    """
    try:
        # Check if user exists and get their current data
        existing_user = execute_query(
            """
            SELECT u.UserId, u.UserEmail, u.UserRoleId, ur.UserRoleName, u.UserCompanyId
            FROM Users u
            INNER JOIN UserRoles ur ON u.UserRoleId = ur.UserRoleId
            WHERE u.UserId = ?
            """,
            (user_id,)
        )
        
        if not existing_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found"
            )
        
        existing_user = existing_user[0]
        
        # Check permissions:
        # 1. Users can update their own info
        # 2. SuperAdmin can update anyone
        # 3. Admin can only update users in their company
        # 4. Driver can only update their own info
        if current_user.user_id != user_id:  # Not updating self
            if current_user.role.value == "Driver":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Drivers can only update their own information"
                )
            elif current_user.role.value == "Admin":
                # Admin can only update users in their company
                if existing_user["UserCompanyId"] != current_user.company_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Admins can only update users in their company"
                    )
        
        # Validate company exists if company_id is being updated
        if user_data.company_id is not None:
            # Only SuperAdmin can change company_id
            if current_user.role.value != "SuperAdmin":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only SuperAdmin can change user's company"
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
        
        # Update user
        update_fields = []
        update_values = []
        
        if user_data.first_name is not None:
            update_fields.append("UserFirstName = ?")
            update_values.append(user_data.first_name)
        
        if user_data.last_name is not None:
            update_fields.append("UserLastName = ?")
            update_values.append(user_data.last_name)
        
        if user_data.phone is not None:
            update_fields.append("UserPhone = ?")
            update_values.append(user_data.phone)
        
        if user_data.company_id is not None:
            update_fields.append("UserCompanyId = ?")
            update_values.append(user_data.company_id)
        
        if user_data.password is not None:
            # Only SuperAdmin or the user themselves can change password
            if current_user.role.value != "SuperAdmin" and current_user.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only SuperAdmin or the user themselves can change password"
                )
            update_fields.append("UserPasswordHash = ?")
            update_values.append(AuthService.hash_password(user_data.password))
        
        if not update_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update"
            )
        
        update_fields.append("UserUpdated = ?")
        update_values.append(datetime.now().isoformat())
        update_values.append(user_id)
        
        execute_insert(
            f"""
            UPDATE Users 
            SET {', '.join(update_fields)}
            WHERE UserId = ?
            """,
            tuple(update_values)
        )
        
        # Get updated user
        updated_user = execute_query(
            """
            SELECT u.UserId, u.UserEmail, u.UserFirstName, u.UserLastName,
                   u.UserPhone, u.UserCompanyId, ur.UserRoleName,
                   u.UserCreated, u.UserUpdated
            FROM Users u
            INNER JOIN UserRoles ur ON u.UserRoleId = ur.UserRoleId
            WHERE u.UserId = ?
            """,
            (user_id,)
        )[0]
        
        logger.info(f"✅ User updated: {updated_user['UserEmail']} by {current_user.email} ({current_user.role})")
        
        return User(
            user_id=updated_user["UserId"],
            email=updated_user["UserEmail"],
            first_name=updated_user["UserFirstName"],
            last_name=updated_user["UserLastName"],
            role=updated_user["UserRoleName"],
            company_id=updated_user["UserCompanyId"],
            phone=updated_user["UserPhone"],
            created_at=updated_user["UserCreated"],
            updated_at=updated_user["UserUpdated"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error updating user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user"
        )

@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    current_user: UserInToken = Depends(require_admin_or_higher)
):
    """
    Delete a user (Admin or SuperAdmin only).
    
    Args:
        user_id: ID of user to delete
        current_user: Current user (must be Admin or SuperAdmin)
    """
    try:
        # Check if user exists and get their current data
        existing_user = execute_query(
            """
            SELECT u.UserId, u.UserEmail, u.UserCompanyId, ur.UserRoleName
            FROM Users u
            INNER JOIN UserRoles ur ON u.UserRoleId = ur.UserRoleId
            WHERE u.UserId = ?
            """,
            (user_id,)
        )
        
        if not existing_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found"
            )
        
        existing_user = existing_user[0]
        
        # Check permissions:
        # 1. Users cannot delete themselves
        # 2. SuperAdmin can delete anyone
        # 3. Admin can only delete users in their company
        if user_id == current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete your own account"
            )
        
        if current_user.role.value == "Admin":
            # Admin can only delete users in their company
            if existing_user["UserCompanyId"] != current_user.company_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Admins can only delete users in their company"
                )
            
            # Admin cannot delete SuperAdmin users
            if existing_user["UserRoleName"] == "SuperAdmin":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Admins cannot delete SuperAdmin users"
                )
        
        # Delete user
        rows_affected = execute_delete(
            "DELETE FROM Users WHERE UserId = ?",
            (user_id,)
        )
        
        if rows_affected <= 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete user"
            )
        
        logger.info(f"✅ User deleted: {existing_user['UserEmail']} by {current_user.email} ({current_user.role})")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete user"
        )