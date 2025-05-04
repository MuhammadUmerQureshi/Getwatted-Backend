from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel

class RFIDCardCreate(BaseModel):
    """Schema for creating a new RFID card."""
    RFIDCardId: str
    RFIDCardCompanyId: int
    RFIDCardDriverId: int
    RFIDCardEnabled: bool = True
    RFIDCardNameOn: Optional[str] = None
    RFIDCardNumberOn: Optional[str] = None
    RFIDCardExpiration: Optional[date] = None

class RFIDCardUpdate(BaseModel):
    """Schema for updating an RFID card."""
    RFIDCardDriverId: Optional[int] = None
    RFIDCardEnabled: Optional[bool] = None
    RFIDCardNameOn: Optional[str] = None
    RFIDCardNumberOn: Optional[str] = None
    RFIDCardExpiration: Optional[date] = None

class RFIDCard(BaseModel):
    """RFID card model representing an RFID card in the database."""
    RFIDCardId: str
    RFIDCardCompanyId: int
    RFIDCardDriverId: int
    RFIDCardEnabled: bool
    RFIDCardNameOn: Optional[str] = None
    RFIDCardNumberOn: Optional[str] = None
    RFIDCardExpiration: Optional[date] = None
    RFIDCardCreated: datetime
    RFIDCardUpdated: datetime

    class Config:
        from_attributes = True