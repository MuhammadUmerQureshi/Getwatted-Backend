from datetime import datetime, time
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ChargerCreate(BaseModel):
    """Schema for creating a new charger."""
    ChargerId: int
    ChargerCompanyId: int
    ChargerSiteId: int
    ChargerName: str
    ChargerEnabled: bool = True
    ChargerBrand: Optional[str] = None
    ChargerModel: Optional[str] = None
    ChargerType: Optional[str] = None
    ChargerSerial: Optional[str] = None
    ChargerMeter: Optional[str] = None
    ChargerMeterSerial: Optional[str] = None
    ChargerPincode: Optional[str] = None
    ChargerWsURL: Optional[str] = None
    ChargerICCID: Optional[str] = None
    ChargerAvailability: Optional[str] = None
    ChargerIsOnline: bool = False
    ChargerAccessType: Optional[str] = None
    ChargerActive24x7: bool = True
    ChargerGeoCoord: Optional[str] = None
    ChargerPaymentMethodId: Optional[int] = None
    ChargerPhoto: Optional[str] = None
    ChargerFirmwareVersion: Optional[str] = None


class ChargerUpdate(BaseModel):
    """Schema for updating a charger."""
    ChargerCompanyId: Optional[int] = None
    ChargerSiteId: Optional[int] = None
    ChargerName: Optional[str] = None
    ChargerEnabled: Optional[bool] = None
    ChargerBrand: Optional[str] = None
    ChargerModel: Optional[str] = None
    ChargerType: Optional[str] = None
    ChargerSerial: Optional[str] = None
    ChargerMeter: Optional[str] = None
    ChargerMeterSerial: Optional[str] = None
    ChargerPincode: Optional[str] = None
    ChargerWsURL: Optional[str] = None
    ChargerICCID: Optional[str] = None
    ChargerAvailability: Optional[str] = None
    ChargerIsOnline: Optional[bool] = None
    ChargerAccessType: Optional[str] = None
    ChargerActive24x7: Optional[bool] = None
    ChargerGeoCoord: Optional[str] = None
    ChargerPaymentMethodId: Optional[int] = None
    ChargerPhoto: Optional[str] = None
    ChargerFirmwareVersion: Optional[str] = None
    ChargerMonFrom: Optional[time] = None
    ChargerMonTo: Optional[time] = None
    ChargerTueFrom: Optional[time] = None
    ChargerTueTo: Optional[time] = None
    ChargerWedFrom: Optional[time] = None
    ChargerWedTo: Optional[time] = None
    ChargerThuFrom: Optional[time] = None
    ChargerThuTo: Optional[time] = None
    ChargerFriFrom: Optional[time] = None
    ChargerFriTo: Optional[time] = None
    ChargerSatFrom: Optional[time] = None
    ChargerSatTo: Optional[time] = None
    ChargerSunFrom: Optional[time] = None
    ChargerSunTo: Optional[time] = None

    class Config:
        from_attributes = True


class Charger(BaseModel):
    """Charger model representing a charger in the database."""
    ChargerId: int
    ChargerCompanyId: int
    ChargerSiteId: int
    ChargerName: str
    ChargerEnabled: bool
    ChargerBrand: Optional[str] = None
    ChargerModel: Optional[str] = None
    ChargerType: Optional[str] = None
    ChargerSerial: Optional[str] = None
    ChargerMeter: Optional[str] = None
    ChargerMeterSerial: Optional[str] = None
    ChargerPincode: Optional[str] = None
    ChargerWsURL: Optional[str] = None
    ChargerICCID: Optional[str] = None
    ChargerAvailability: Optional[str] = None
    ChargerIsOnline: bool
    ChargerAccessType: Optional[str] = None
    ChargerActive24x7: bool
    ChargerGeoCoord: Optional[str] = None
    ChargerLastConn: Optional[datetime] = None
    ChargerLastDisconn: Optional[datetime] = None
    ChargerLastHeartbeat: Optional[datetime] = None
    ChargerPhoto: Optional[str] = None
    ChargerFirmwareVersion: Optional[str] = None
    ChargerPaymentMethodId: Optional[int] = None
    ChargerMonFrom: Optional[time] = None
    ChargerMonTo: Optional[time] = None
    ChargerTueFrom: Optional[time] = None
    ChargerTueTo: Optional[time] = None
    ChargerWedFrom: Optional[time] = None
    ChargerWedTo: Optional[time] = None
    ChargerThuFrom: Optional[time] = None
    ChargerThuTo: Optional[time] = None
    ChargerFriFrom: Optional[time] = None
    ChargerFriTo: Optional[time] = None
    ChargerSatFrom: Optional[time] = None
    ChargerSatTo: Optional[time] = None
    ChargerSunFrom: Optional[time] = None
    ChargerSunTo: Optional[time] = None
    ChargerCreated: datetime
    ChargerUpdated: datetime

    class Config:
        from_attributes = True


class ConnectorCreate(BaseModel):
    """Schema for creating a new connector."""
    ConnectorId: int
    ConnectorCompanyId: int
    ConnectorSiteId: int
    ConnectorChargerId: int
    ConnectorType: Optional[str] = None
    ConnectorEnabled: bool = True
    ConnectorStatus: Optional[str] = None
    ConnectorMaxVolt: Optional[float] = None
    ConnectorMaxAmp: Optional[float] = None


class ConnectorUpdate(BaseModel):
    """Schema for updating a connector."""
    ConnectorType: Optional[str] = None
    ConnectorEnabled: Optional[bool] = None
    ConnectorStatus: Optional[str] = None
    ConnectorMaxVolt: Optional[float] = None
    ConnectorMaxAmp: Optional[float] = None


class Connector(BaseModel):
    """Connector model representing a connector in the database."""
    ConnectorId: int
    ConnectorCompanyId: int
    ConnectorSiteId: int
    ConnectorChargerId: int
    ConnectorType: Optional[str] = None
    ConnectorEnabled: bool
    ConnectorStatus: Optional[str] = None
    ConnectorMaxVolt: Optional[float] = None
    ConnectorMaxAmp: Optional[float] = None
    ConnectorCreated: datetime
    ConnectorUpdated: datetime

    class Config:
        from_attributes = True