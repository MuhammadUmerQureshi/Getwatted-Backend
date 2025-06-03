# app/services/auth_service.py
import jwt
import bcrypt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import HTTPException, status
import logging

from app.config.auth_config import auth_settings, ROLE_HIERARCHY
from app.models.auth import UserInToken, TokenPayload, UserRole
from app.db.database import execute_query, execute_insert, execute_update

logger = logging.getLogger("ocpp.auth")

class AuthService:
    """Service for handling authentication operations."""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt."""
        salt = bcrypt.gensalt(rounds=auth_settings.password_bcrypt_rounds)
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    @staticmethod
    def verify_password(password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))
    
    @staticmethod
    def create_access_token(user_data: Dict[str, Any]) -> str:
        """Create a JWT access token."""
        try:
            # Create expiration time
            expire = datetime.utcnow() + timedelta(hours=auth_settings.jwt_access_token_expire_hours)
            
            # Create payload
            payload = {
                "user_id": user_data["user_id"],
                "email": user_data["email"],
                "role": user_data["role"],
                "company_id": user_data.get("company_id"),
                "driver_id": user_data.get("driver_id"),
                "exp": expire,
                "iat": datetime.utcnow()
            }
            
            # Encode token
            token = jwt.encode(
                payload, 
                auth_settings.jwt_secret_key, 
                algorithm=auth_settings.jwt_algorithm
            )
            
            logger.info(f"✅ Access token created for user {user_data['email']}")
            return token
            
        except Exception as e:
            logger.error(f"❌ Error creating access token: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not create access token"
            )
    
    @staticmethod
    def verify_token(token: str) -> UserInToken:
        """Verify and decode a JWT token."""
        try:
            # Decode token
            payload = jwt.decode(
                token, 
                auth_settings.jwt_secret_key, 
                algorithms=[auth_settings.jwt_algorithm]
            )
            
            # Extract user data
            user = UserInToken(
                user_id=payload["user_id"],
                email=payload["email"],
                role=UserRole(payload["role"]),
                company_id=payload.get("company_id"),
                driver_id=payload.get("driver_id")
            )
            
            return user
            
        except jwt.ExpiredSignatureError:
            logger.warning("⚠️ Token expired")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired",
                headers={"WWW-Authenticate": "Bearer"}
            )
        except jwt.JWTError as e:
            logger.warning(f"⚠️ Invalid token: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"}
            )
    
    @staticmethod
    def authenticate_user(email: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate a user with email and password."""
        try:
            # Get user from database
            user = execute_query(
                """
                SELECT u.UserId, u.UserEmail, u.UserFirstName, u.UserLastName, 
                       u.UserPhone, u.UserCompanyId, ur.UserRoleName,
                       u.UserPasswordHash, d.DriverId
                FROM Users u
                INNER JOIN UserRoles ur ON u.UserRoleId = ur.UserRoleId
                LEFT JOIN Drivers d ON u.UserId = d.DriverUserId
                WHERE u.UserEmail = ?
                """,
                (email,)
            )
            
            if not user:
                logger.warning(f"⚠️ User not found: {email}")
                return None
            
            user_data = user[0]
            
            # Verify password
            if not AuthService.verify_password(password, user_data["UserPasswordHash"]):
                logger.warning(f"⚠️ Invalid password for user: {email}")
                return None
            
            # Return user data
            return {
                "user_id": user_data["UserId"],
                "email": user_data["UserEmail"],
                "first_name": user_data["UserFirstName"],
                "last_name": user_data["UserLastName"],
                "role": user_data["UserRoleName"],
                "company_id": user_data["UserCompanyId"],
                "driver_id": user_data.get("DriverId"),
                "phone": user_data["UserPhone"]
            }
            
        except Exception as e:
            logger.error(f"❌ Error authenticating user: {str(e)}")
            return None
    
    @staticmethod
    def check_role_permission(user_role: str, required_role: str) -> bool:
        """Check if user role has permission for required role."""
        user_level = ROLE_HIERARCHY.get(user_role, 0)
        required_level = ROLE_HIERARCHY.get(required_role, 999)
        return user_level >= required_level
    
    @staticmethod
    def check_company_access(user: UserInToken, company_id: int) -> bool:
        """Check if user can access the specified company."""
        # SuperAdmin can access any company
        if user.role == UserRole.SUPER_ADMIN:
            return True
        
        # Others can only access their own company
        return user.company_id == company_id