# app/models/session.py
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel

class ChargeSessionCreate(BaseModel):
    """Schema for creating a new charge session."""
    ChargerSessionCompanyId: int
    ChargerSessionSiteId: int
    ChargerSessionChargerId: int
    ChargerSessionConnectorId: int
    ChargerSessionDriverId: Optional[int] = None
    ChargerSessionRFIDCard: Optional[str] = None
    ChargerSessionStart: datetime
    ChargerSessionStatus: str = "Started"
    
class ChargeSessionUpdate(BaseModel):
    """Schema for updating a charge session."""
    ChargerSessionEnd: Optional[datetime] = None
    ChargerSessionDuration: Optional[int] = None
    ChargerSessionReason: Optional[str] = None
    ChargerSessionStatus: Optional[str] = None
    ChargerSessionEnergyKWH: Optional[float] = None
    ChargerSessionPricingPlanId: Optional[int] = None
    ChargerSessionCost: Optional[float] = None
    ChargerSessionDiscountId: Optional[int] = None
    ChargerSessionPaymentId: Optional[int] = None
    ChargerSessionPaymentAmount: Optional[float] = None
    ChargerSessionPaymentStatus: Optional[str] = None

class ChargeSession(BaseModel):
    """Charge session model representing a charging session in the database."""
    ChargeSessionId: int
    ChargerSessionCompanyId: int
    ChargerSessionSiteId: int
    ChargerSessionChargerId: int
    ChargerSessionConnectorId: int
    ChargerSessionDriverId: Optional[int] = None
    ChargerSessionRFIDCard: Optional[str] = None
    ChargerSessionStart: datetime
    ChargerSessionEnd: Optional[datetime] = None
    ChargerSessionDuration: Optional[int] = None
    ChargerSessionReason: Optional[str] = None
    ChargerSessionStatus: str
    ChargerSessionEnergyKWH: Optional[float] = None
    ChargerSessionPricingPlanId: Optional[int] = None
    ChargerSessionCost: Optional[float] = None
    ChargerSessionDiscountId: Optional[int] = None
    ChargerSessionPaymentId: Optional[int] = None
    ChargerSessionPaymentAmount: Optional[float] = None
    ChargerSessionPaymentStatus: Optional[str] = None
    ChargerSessionCreated: datetime
    
    class Config:
        from_attributes = True

class EventDataCreate(BaseModel):
    """Schema for creating a new event data record."""
    EventsDataCompanyId: int
    EventsDataSiteId: int
    EventsDataChargerId: int
    EventsDataConnectorId: Optional[int] = None
    EventsDataSessionId: Optional[int] = None
    EventsDataDateTime: datetime
    EventsDataType: str
    EventsDataTriggerReason: Optional[str] = None
    EventsDataOrigin: str = "ChargePoint"
    EventsDataData: str
    EventsDataTemperature: Optional[float] = None
    EventsDataCurrent: Optional[float] = None
    EventsDataVoltage: Optional[float] = None
    EventsDataMeterValue: Optional[float] = None

class EventData(BaseModel):
    """Event data model representing an event in the database."""
    EventsDataNumber: int
    EventsDataCompanyId: int
    EventsDataSiteId: int
    EventsDataChargerId: int
    EventsDataConnectorId: Optional[int] = None
    EventsDataSessionId: Optional[int] = None
    EventsDataDateTime: datetime
    EventsDataType: str
    EventsDataTriggerReason: Optional[str] = None
    EventsDataOrigin: str
    EventsDataData: str
    EventsDataTemperature: Optional[float] = None
    EventsDataCurrent: Optional[float] = None
    EventsDataVoltage: Optional[float] = None
    EventsDataMeterValue: Optional[float] = None
    EventsDataCreated: datetime
    
    class Config:
        from_attributes = True