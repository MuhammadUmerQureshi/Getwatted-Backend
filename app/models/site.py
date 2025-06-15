from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class SiteCreate(BaseModel):
    """Schema for creating a new site."""
    SiteName: str
    SiteCompanyID: int = Field(..., alias="company_id")
    SiteEnabled: bool = True
    SiteGroupId: Optional[int] = None
    SiteAddress: Optional[str] = None
    SiteCity: Optional[str] = None
    SiteRegion: Optional[str] = None
    SiteCountry: Optional[str] = None
    SiteZipCode: Optional[str] = None
    SiteGeoCoord: Optional[str] = None
    SiteTaxRate: Optional[float] = None
    SiteContactName: Optional[str] = None
    SiteContactPh: Optional[str] = None
    SiteContactEmail: Optional[str] = None

    class Config:
        populate_by_name = True


class SiteUpdate(BaseModel):
    """Schema for updating a site."""
    SiteName: Optional[str] = Field(None, alias="name")
    SiteEnabled: Optional[bool] = Field(None, alias="enabled")
    SiteGroupId: Optional[int] = Field(None, alias="group_id")
    SiteAddress: Optional[str] = Field(None, alias="address")
    SiteCity: Optional[str] = Field(None, alias="city")
    SiteRegion: Optional[str] = Field(None, alias="region")
    SiteCountry: Optional[str] = Field(None, alias="country")
    SiteZipCode: Optional[str] = Field(None, alias="zip_code")
    SiteGeoCoord: Optional[str] = Field(None, alias="geo_coord")
    SiteTaxRate: Optional[float] = Field(None, alias="tax_rate")
    SiteContactName: Optional[str] = Field(None, alias="contact_name")
    SiteContactPh: Optional[str] = Field(None, alias="contact_ph")
    SiteContactEmail: Optional[str] = Field(None, alias="contact_email")
    SiteCompanyID: Optional[int] = Field(None, alias="company_id", exclude=True)

    class Config:
        populate_by_name = True
        extra = "ignore"


class Site(BaseModel):
    """Site model representing a site in the database."""
    SiteId: int
    SiteCompanyID: int
    SiteEnabled: bool
    SiteName: str
    SiteGroupId: Optional[int] = None
    SiteAddress: Optional[str] = None
    SiteCity: Optional[str] = None
    SiteRegion: Optional[str] = None
    SiteCountry: Optional[str] = None
    SiteZipCode: Optional[str] = None
    SiteGeoCoord: Optional[str] = None
    SiteTaxRate: Optional[float] = None
    SiteContactName: Optional[str] = None
    SiteContactPh: Optional[str] = None
    SiteContactEmail: Optional[str] = None
    SiteCreated: datetime
    SiteUpdated: datetime

    class Config:
        from_attributes = True