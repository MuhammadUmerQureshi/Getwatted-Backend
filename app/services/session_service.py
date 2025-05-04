# app/services/session_service.py
import logging
from datetime import datetime
import json
from app.db.database import execute_query, execute_insert, execute_update
from app.db.charge_point_db import get_charger_info, log_event

logger = logging.getLogger("ocpp.session")

def get_active_session_by_connector(charger_id, company_id, site_id, connector_id):
    """
    Get an active charging session for a specific connector.
    
    Args:
        charger_id (int): The ID of the charger
        company_id (int): The ID of the company
        site_id (int): The ID of the site
        connector_id (int): The ID of the connector
        
    Returns:
        dict: Session information or None if not found
    """
    try:
        session = execute_query(
            """
            SELECT * FROM ChargeSessions 
            WHERE ChargerSessionChargerId = ? AND ChargerSessionCompanyId = ? 
            AND ChargerSessionSiteId = ? AND ChargerSessionConnectorId = ?
            AND ChargerSessionEnd IS NULL
            """,
            (charger_id, company_id, site_id, connector_id)
        )
        
        if session:
            return session[0]
        else:
            return None
            
    except Exception as e:
        logger.error(f"❌ DATABASE ERROR: Failed to get active session: {str(e)}")
        return None

def calculate_session_energy(session_id):
    """
    Calculate the energy consumed during a session based on meter values.
    
    Args:
        session_id (int): The ID of the charge session
        
    Returns:
        float: Total energy consumed in kWh or 0 if error
    """
    try:
        # Get meter start value
        start_event = execute_query(
            """
            SELECT EventsDataMeterValue
            FROM EventsData
            WHERE EventsDataSessionId = ? AND EventsDataType = 'StartTransaction'
            LIMIT 1
            """,
            (session_id,)
        )
        
        start_value = 0
        if start_event and start_event[0]["EventsDataMeterValue"] is not None:
            start_value = start_event[0]["EventsDataMeterValue"]
        
        # Get meter stop value
        stop_event = execute_query(
            """
            SELECT EventsDataMeterValue
            FROM EventsData
            WHERE EventsDataSessionId = ? AND EventsDataType = 'StopTransaction'
            LIMIT 1
            """,
            (session_id,)
        )
        
        stop_value = 0
        if stop_event and stop_event[0]["EventsDataMeterValue"] is not None:
            stop_value = stop_event[0]["EventsDataMeterValue"]
        
        # Calculate energy
        energy_kwh = (stop_value - start_value) / 1000.0  # Convert Wh to kWh
        
        return max(0, energy_kwh)  # Ensure non-negative value
        
    except Exception as e:
        logger.error(f"❌ DATABASE ERROR: Failed to calculate session energy: {str(e)}")
        return 0

def get_session_meter_timeline(session_id):
    """
    Get a timeline of meter values for a specific session.
    
    Args:
        session_id (int): The ID of the charge session
        
    Returns:
        list: Timeline of meter values
    """
    try:
        meter_events = execute_query(
            """
            SELECT EventsDataDateTime, EventsDataMeterValue, EventsDataCurrent, EventsDataVoltage
            FROM EventsData
            WHERE EventsDataSessionId = ? AND EventsDataMeterValue IS NOT NULL
            ORDER BY EventsDataDateTime
            """,
            (session_id,)
        )
        
        return meter_events
        
    except Exception as e:
        logger.error(f"❌ DATABASE ERROR: Failed to get session meter timeline: {str(e)}")
        return []

def track_max_power(session_id):
    """
    Calculate the maximum power during a charge session.
    
    Args:
        session_id (int): The ID of the charge session
        
    Returns:
        float: Maximum power in kW or 0 if error
    """
    try:
        # Find maximum power by looking at current and voltage readings
        power_readings = execute_query(
            """
            SELECT EventsDataCurrent * EventsDataVoltage / 1000.0 as power_kw
            FROM EventsData
            WHERE EventsDataSessionId = ? 
            AND EventsDataCurrent IS NOT NULL 
            AND EventsDataVoltage IS NOT NULL
            """,
            (session_id,)
        )
        
        if not power_readings:
            return 0
            
        max_power = 0
        for reading in power_readings:
            if reading["power_kw"] > max_power:
                max_power = reading["power_kw"]
                
        return max_power
        
    except Exception as e:
        logger.error(f"❌ DATABASE ERROR: Failed to calculate max power: {str(e)}")
        return 0