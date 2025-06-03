# app/models/auth.py
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, field_validator
from enum import Enum
import re

class UserRole(str, Enum):
    SUPER_ADMIN = "SuperAdmin"
    ADMIN = "Admin"
    DRIVER = "Driver"

class LoginRequest(BaseModel):
    """Login request model."""
    email: str  # Changed from EmailStr to str
    password: str
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        """Custom email validation that allows .local domains"""
        if not v or '@' not in v:
            raise ValueError('Invalid email format')
        
        # Basic email pattern that allows .local and other development domains
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$|^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.local$'
        if not re.match(email_pattern, v):
            raise ValueError('Invalid email format')
        
        return v.lower()

class LoginResponse(BaseModel):
    """Login response model."""
    access_token: str
    token_type: str = "bearer"
    user: "UserInfo"

class UserInfo(BaseModel):
    """User information model."""
    user_id: int
    email: str
    role: UserRole
    company_id: Optional[int] = None
    driver_id: Optional[int] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None

class UserInToken(BaseModel):
    """User model for JWT token payload."""
    user_id: int
    email: str
    role: UserRole
    company_id: Optional[int] = None
    driver_id: Optional[int] = None

class TokenPayload(BaseModel):
    """JWT token payload model."""
    user_id: int
    email: str
    role: str
    company_id: Optional[int] = None
    driver_id: Optional[int] = None
    exp: int
    iat: int

class UserCreate(BaseModel):
    """Schema for creating a new user."""
    email: str  # Changed from EmailStr to str
    password: str
    first_name: str
    last_name: str
    role: UserRole
    company_id: Optional[int] = None  # Required for Admin/Driver, None for SuperAdmin
    phone: Optional[str] = None
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        """Custom email validation that allows .local domains"""
        if not v or '@' not in v:
            raise ValueError('Invalid email format')
        
        # Basic email pattern that allows .local and other development domains
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$|^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.local'
        if not re.match(email_pattern, v):
            raise ValueError('Invalid email format')
        
        return v.lower()

class UserUpdate(BaseModel):
    """Schema for updating a user."""
    email: Optional[str] = None  # Changed from EmailStr to str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: Optional[UserRole] = None
    company_id: Optional[int] = None
    phone: Optional[str] = None
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        """Custom email validation that allows .local domains"""
        if v is None:
            return v
        if not v or '@' not in v:
            raise ValueError('Invalid email format')
        # Basic email pattern that allows .local and other development domains
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$|^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.local$'
        if not re.match(email_pattern, v):
            raise ValueError('Invalid email format')
        
        return v.lower()

class User(BaseModel):
    """User model representing a user in the database."""
    user_id: int
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: UserRole
    company_id: Optional[int] = None
    driver_id: Optional[int] = None
    phone: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True