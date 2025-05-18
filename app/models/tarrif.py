from datetime import datetime, time
from typing import Optional
from pydantic import BaseModel, Field


class TariffCreate(BaseModel):
    """Schema for creating a new tariff."""
    TariffsName: str
    TariffsCompanyId: int
    TariffsEnabled: bool = True
    TariffsType: Optional[str] = None
    TariffsPer: Optional[str] = None
    TariffsRateDaytime: Optional[float] = None
    TariffsRateNighttime: Optional[float] = None
    TariffsDaytimeFrom: Optional[time] = None
    TariffsDaytimeTo: Optional[time] = None
    TariffsNighttimeFrom: Optional[time] = None
    TariffsNighttimeTo: Optional[time] = None
    TariffsFixedStartFee: Optional[float] = None
    TariffsIdleChargingFee: Optional[float] = None
    TariffsIdleApplyAfter: Optional[int] = None


class TariffUpdate(BaseModel):
    """Schema for updating a tariff."""
    TariffsName: Optional[str] = None
    TariffsEnabled: Optional[bool] = None
    TariffsType: Optional[str] = None
    TariffsPer: Optional[str] = None
    TariffsRateDaytime: Optional[float] = None
    TariffsRateNighttime: Optional[float] = None
    TariffsDaytimeFrom: Optional[time] = None
    TariffsDaytimeTo: Optional[time] = None
    TariffsNighttimeFrom: Optional[time] = None
    TariffsNighttimeTo: Optional[time] = None
    TariffsFixedStartFee: Optional[float] = None
    TariffsIdleChargingFee: Optional[float] = None
    TariffsIdleApplyAfter: Optional[int] = None


class Tariff(BaseModel):
    """Tariff model representing a tariff in the database."""
    TariffsId: int
    TariffsCompanyId: int
    TariffsEnabled: bool
    TariffsName: str
    TariffsType: Optional[str] = None
    TariffsPer: Optional[str] = None
    TariffsRateDaytime: Optional[float] = None
    TariffsRateNighttime: Optional[float] = None
    TariffsDaytimeFrom: Optional[time] = None
    TariffsDaytimeTo: Optional[time] = None
    TariffsNighttimeFrom: Optional[time] = None
    TariffsNighttimeTo: Optional[time] = None
    TariffsFixedStartFee: Optional[float] = None
    TariffsIdleChargingFee: Optional[float] = None
    TariffsIdleApplyAfter: Optional[int] = None
    TariffsCreated: datetime
    TariffsUpdated: datetime

    class Config:
        from_attributes = True