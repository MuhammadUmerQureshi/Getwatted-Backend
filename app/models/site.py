from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class SiteCreate(BaseModel):
    """Schema for creating a new site."""
    SiteName: str
    SiteCompanyID: int
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


class SiteUpdate(BaseModel):
    """Schema for updating a site."""
    SiteName: Optional[str] = None
    SiteEnabled: Optional[bool] = None
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