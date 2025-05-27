# app/models/driver.py
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class DriverCreate(BaseModel):
    """Schema for creating a new driver."""
    DriverCompanyId: int
    DriverFullName: str
    DriverEnabled: bool = True
    DriverEmail: Optional[str] = None
    DriverPhone: Optional[str] = None
    DriverGroupId: Optional[int] = None
    DriverNotifActions: bool = False
    DriverNotifPayments: bool = False
    DriverNotifSystem: bool = False

class DriverUpdate(BaseModel):
    """Schema for updating a driver."""
    DriverFullName: Optional[str] = None
    DriverEnabled: Optional[bool] = None
    DriverEmail: Optional[str] = None
    DriverPhone: Optional[str] = None
    DriverGroupId: Optional[int] = None
    DriverNotifActions: Optional[bool] = None
    DriverNotifPayments: Optional[bool] = None
    DriverNotifSystem: Optional[bool] = None

class Driver(BaseModel):
    """Driver model representing a driver in the database."""
    DriverId: int
    DriverCompanyId: int
    DriverEnabled: bool
    DriverFullName: str
    DriverEmail: Optional[str] = None
    DriverPhone: Optional[str] = None
    DriverGroupId: Optional[int] = None
    DriverNotifActions: bool
    DriverNotifPayments: bool
    DriverNotifSystem: bool
    DriverCreated: datetime
    DriverUpdated: datetime

    class Config:
        from_attributes = True