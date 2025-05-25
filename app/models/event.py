# app/models/event.py
from datetime import datetime
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field


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


class EventSummary(BaseModel):
    """Summary statistics for events."""
    total_events: int
    event_types: Dict[str, int]
    date_range: Dict[str, Optional[str]]
    latest_event: Optional[datetime] = None


class EventTypeStats(BaseModel):
    """Statistics by event type."""
    event_type: str
    count: int
    latest_occurrence: Optional[datetime] = None
    earliest_occurrence: Optional[datetime] = None