from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class DriverGroupCreate(BaseModel):
    """Schema for creating a new driver group."""
    DriversGroupName: str
    DriversGroupCompanyId: int
    DriversGroupEnabled: bool = True
    DriversGroupDiscountId: Optional[int] = None
    DriverTariffId: Optional[int] = None


class DriverGroupUpdate(BaseModel):
    """Schema for updating a driver group."""
    DriversGroupName: Optional[str] = None
    DriversGroupEnabled: Optional[bool] = None
    DriversGroupDiscountId: Optional[int] = None
    DriverTariffId: Optional[int] = None


class DriverGroup(BaseModel):
    """Driver group model representing a driver group in the database."""
    DriversGroupId: int
    DriversGroupCompanyId: int
    DriversGroupName: str
    DriversGroupEnabled: bool
    DriversGroupDiscountId: Optional[int] = None
    DriverTariffId: Optional[int] = None
    DriversGroupCreated: datetime
    DriversGroupUpdated: datetime

    class Config:
        from_attributes = True