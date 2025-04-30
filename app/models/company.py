from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class CompanyCreate(BaseModel):
    """Schema for creating a new company."""
    CompanyName: str
    CompanyEnabled: bool = True
    CompanyHomePhoto: Optional[str] = None
    CompanyBrandColour: Optional[str] = None
    CompanyBrandLogo: Optional[str] = None
    CompanyBrandFavicon: Optional[str] = None


class CompanyUpdate(BaseModel):
    """Schema for updating a company."""
    CompanyName: Optional[str] = None
    CompanyEnabled: Optional[bool] = None
    CompanyHomePhoto: Optional[str] = None
    CompanyBrandColour: Optional[str] = None
    CompanyBrandLogo: Optional[str] = None
    CompanyBrandFavicon: Optional[str] = None


class Company(BaseModel):
    """Company model representing a company in the database."""
    CompanyId: int
    CompanyName: str
    CompanyEnabled: bool
    CompanyHomePhoto: Optional[str] = None
    CompanyBrandColour: Optional[str] = None
    CompanyBrandLogo: Optional[str] = None
    CompanyBrandFavicon: Optional[str] = None
    CompanyCreated: datetime
    CompanyUpdated: datetime

    class Config:
        from_attributes = True