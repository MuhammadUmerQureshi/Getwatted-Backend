from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class SiteGroupCreate(BaseModel):
    """Schema for creating a new site group."""
    SiteGroupName: str
    SiteCompanyId: int
    SiteGroupEnabled: bool = True


class SiteGroupUpdate(BaseModel):
    """Schema for updating a site group."""
    SiteGroupName: Optional[str] = None
    SiteGroupEnabled: Optional[bool] = None


class SiteGroup(BaseModel):
    """Site group model representing a site group in the database."""
    SiteGroupId: int
    SiteCompanyId: int
    SiteGroupName: str
    SiteGroupEnabled: bool
    SiteGroupCreated: datetime
    SiteGroupUpdated: datetime

    class Config:
        from_attributes = True