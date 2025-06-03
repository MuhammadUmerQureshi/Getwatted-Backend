# app/config/auth_config.py
from pydantic_settings import BaseSettings
from typing import Optional
import os

class AuthSettings(BaseSettings):
    """Authentication configuration settings."""
    
    # JWT Configuration
    jwt_secret_key: str = "your-super-secret-jwt-key-change-this-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_hours: int = 24
    
    # Password hashing
    password_bcrypt_rounds: int = 12
    
    # Security
    allow_user_registration: bool = False  # Only admins can create users
    
    class Config:
        env_file = ".env"
        env_prefix = "AUTH_"
        extra = "ignore"

# Global auth settings instance
auth_settings = AuthSettings()

# Role hierarchy for permission checking
ROLE_HIERARCHY = {
    "SuperAdmin": 3,
    "Admin": 2,
    "Driver": 1
}