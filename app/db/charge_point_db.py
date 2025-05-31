"""
Database operations for OCPP charge points.
This module contains functions for interacting with the database
for charge point related operations.
"""
import logging
from datetime import datetime
import json
from app.db.database import execute_query, execute_update, execute_insert

logger = logging.getLogger("ocpp.db")

def get_charger_info(charger_name):
    """
    Get charger information from database by charger name.
    
    Args:
        charger_name (str): The name/ID of the charger
        
    Returns:
        dict: Charger information including ID, company ID, and site ID
              or None if charger not found
    """
    try:
        charger_info = execute_query(
            "SELECT ChargerId, ChargerCompanyId, ChargerSiteId FROM Chargers WHERE ChargerName = ?",
            (charger_name,)
        )
        
        if charger_info:
            return {
                'charger_id': charger_info[0]["ChargerId"],
                'company_id': charger_info[0]["ChargerCompanyId"],
                'site_id': charger_info[0]["ChargerSiteId"]
            }
        else:
            logger.error(f"❌ CHARGER NOT FOUND: No charger with name {charger_name} found in database")
            return None
            
    except Exception as e:
        logger.error(f"❌ DATABASE ERROR: Failed to get charger info for {charger_name}: {str(e)}")
        return None

def update_charger_on_boot(charger_name, charger_details):
    """
    Update charger information when boot notification is received.
    
    Args:
        charger_name (str): The name/ID of the charger
        charger_details (dict): Dictionary containing charger details
            {
                'charger_brand': str,
                'charger_model': str,
                'charger_serial': str,
                'firmware_version': str
            }
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        now = datetime.now().isoformat()
        
        # Build update query with only fields that are present
        update_fields = []
        params = []
        
        if charger_details.get('charger_brand'):
            update_fields.append("ChargerBrand = ?")
            params.append(charger_details['charger_brand'])
            
        if charger_details.get('charger_model'):
            update_fields.append("ChargerModel = ?")
            params.append(charger_details['charger_model'])
            
        if charger_details.get('charger_serial'):
            update_fields.append("ChargerSerial = ?")
            params.append(charger_details['charger_serial'])
            
        if charger_details.get('firmware_version'):
            update_fields.append("ChargerFirmwareVersion = ?")
            params.append(charger_details['firmware_version'])
            
        if charger_details.get('charger_meter'):
            update_fields.append("ChargerMeter = ?")
            params.append(charger_details['charger_meter'])
            
        if charger_details.get('charger_meter_serial'):
            update_fields.append("ChargerMeterSerial = ?")
            params.append(charger_details['charger_meter_serial'])
            
        # Always update these fields
        update_fields.append("ChargerIsOnline = ?")
        params.append(1)
        
        update_fields.append("ChargerLastConn = ?")
        params.append(now)
        
        update_fields.append("ChargerUpdated = ?")
        params.append(now)
        
        # Add charger name to params
        params.append(charger_name)
        
        # Execute update if there are fields to update
        if update_fields:
            execute_update(
                f"UPDATE Chargers SET {', '.join(update_fields)} WHERE ChargerName = ?",
                tuple(params)
            )
            logger.info(f"✅ DATABASE UPDATED: Boot notification details for {charger_name}")
            return True
            
        return False
    
    except Exception as e:
        logger.error(f"❌ DATABASE ERROR: Failed to update boot notification details for {charger_name}: {str(e)}")
        return False

def update_charger_heartbeat(charger_name, timestamp):
    """
    Update charger heartbeat timestamp.
    
    Args:
        charger_name (str): The name/ID of the charger
        timestamp (str): ISO format timestamp
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        execute_update(
            """
            UPDATE Chargers
            SET ChargerLastHeartbeat = ?, ChargerIsOnline = ?
            WHERE ChargerName = ?
            """,
            (timestamp, 1, charger_name)
        )
        return True
    
    except Exception as e:
        logger.error(f"❌ DATABASE ERROR: Failed to update heartbeat for {charger_name}: {str(e)}")
        return False

def update_connector_status(charger_info, connector_id, status):
    """
    Update connector status or create a new connector if it doesn't exist.
    
    Args:
        charger_info (dict): Dictionary with charger_id, company_id, site_id
        connector_id (int): ID of the connector
        status (str): New status of the connector
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        if not charger_info:
            logger.error("❌ No charger info provided for connector update")
            return False
            
        now = datetime.now().isoformat()
        charger_id = charger_info['charger_id']
        company_id = charger_info['company_id']
        site_id = charger_info['site_id']
        
        # Check if connector exists
        connector = execute_query(
            """
            SELECT 1 FROM Connectors 
            WHERE ConnectorId = ? AND ConnectorChargerId = ? AND 
                ConnectorCompanyId = ? AND ConnectorSiteId = ?
            """,
            (connector_id, charger_id, company_id, site_id)
        )
        
        if connector:
            # Update existing connector
            execute_update(
                """
                UPDATE Connectors
                SET ConnectorStatus = ?, ConnectorUpdated = ?
                WHERE ConnectorId = ? AND ConnectorChargerId = ? AND 
                    ConnectorCompanyId = ? AND ConnectorSiteId = ?
                """,
                (status, now, connector_id, charger_id, company_id, site_id)
            )
            logger.info(f"✅ CONNECTOR UPDATED: ID {connector_id} on charger {charger_id} status: {status}")
        else:
            # Create new connector record
            execute_insert(
                """
                INSERT INTO Connectors (
                    ConnectorId, ConnectorCompanyId, ConnectorSiteId, ConnectorChargerId,
                    ConnectorStatus, ConnectorEnabled, ConnectorCreated, ConnectorUpdated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (connector_id, company_id, site_id, charger_id, status, 1, now, now)
            )
            logger.info(f"✅ CONNECTOR CREATED: ID {connector_id} on charger {charger_id} status: {status}")
            
        return True
        
    except Exception as e:
        logger.error(f"❌ DATABASE ERROR: Failed to update connector status: {str(e)}")
        return False

def log_event(charger_info, event_type, data, connector_id=None, session_id=None, 
              timestamp=None, meter_value=None, temperature=None, current=None, voltage=None):
    """
    Log an event to the EventsData table.
    
    Args:
        charger_info (dict): Dictionary with charger_id, company_id, site_id
        event_type (str): Type of event (e.g., BootNotification, StatusNotification)
        data (dict): Event data to be stored as JSON
        connector_id (int, optional): ID of the connector involved
        session_id (int, optional): ID of the charge session
        timestamp (str, optional): Event timestamp (default: current time)
        meter_value (float, optional): Meter reading value
        temperature (float, optional): Temperature reading
        current (float, optional): Current reading
        voltage (float, optional): Voltage reading
        
    Returns:
        int: Event ID if successful, None otherwise
    """
    try:
        if not charger_info:
            logger.error("❌ No charger info provided for event logging")
            return None
            
        now = datetime.now().isoformat()
        if timestamp is None:
            timestamp = now
            
        charger_id = charger_info['charger_id']
        company_id = charger_info['company_id']
        site_id = charger_info['site_id']
        
        # Get max event ID
        max_event = execute_query("SELECT MAX(EventsDataNumber) as max_id FROM EventsData")
        new_event_id = 1
        if max_event and max_event[0]['max_id'] is not None:
            new_event_id = max_event[0]['max_id'] + 1
        
        # Convert data to JSON if needed
        if isinstance(data, dict) or isinstance(data, list):
            data_json = json.dumps(data)
        else:
            data_json = json.dumps({"value": str(data)})
            
        # Insert event data
        execute_insert(
            """
            INSERT INTO EventsData (
                EventsDataNumber, EventsDataCompanyId, EventsDataSiteId,
                EventsDataChargerId, EventsDataConnectorId, EventsDataSessionId,
                EventsDataDateTime, EventsDataType, EventsDataOrigin, 
                EventsDataData, EventsDataTemperature, EventsDataCurrent,
                EventsDataVoltage, EventsDataMeterValue, EventsDataCreated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_event_id, company_id, site_id, charger_id,
                connector_id, session_id, timestamp, event_type, 
                "ChargePoint", data_json, temperature, current,
                voltage, meter_value, now
            )
        )
        return new_event_id
        
    except Exception as e:
        logger.error(f"❌ DATABASE ERROR: Failed to log event: {str(e)}")
        return None

def create_charge_session_with_pricing(charger_info, id_tag, connector_id, timestamp, driver_id=None, pricing_plan_id=None, discount_id=None):
    """
    Create a new charge session in the database with pricing plan and discount information.
    
    Args:
        charger_info (dict): Dictionary with charger_id, company_id, site_id
        id_tag (str): The RFID card ID
        connector_id (int): ID of the connector
        timestamp (str): Start time of the session
        driver_id (int, optional): ID of the driver
        pricing_plan_id (int, optional): ID of the pricing plan/tariff
        discount_id (int, optional): ID of the discount
        
    Returns:
        int: Transaction ID of the new session
    """
    try:
        now = datetime.now().isoformat()
        charger_id = charger_info['charger_id']
        company_id = charger_info['company_id']
        site_id = charger_info['site_id']
        
        # Get maximum transaction ID and increment
        max_session = execute_query("SELECT MAX(ChargeSessionId) as max_id FROM ChargeSessions")
        transaction_id = 1
        if max_session and max_session[0]['max_id'] is not None:
            transaction_id = max_session[0]['max_id'] + 1
        
        # Insert new charge session with pricing information
        execute_insert(
            """
            INSERT INTO ChargeSessions (
                ChargeSessionId, ChargerSessionCompanyId, ChargerSessionSiteId,
                ChargerSessionChargerId, ChargerSessionConnectorId, ChargerSessionDriverId,
                ChargerSessionRFIDCard, ChargerSessionStart, ChargerSessionStatus,
                ChargerSessionPricingPlanId, ChargerSessionDiscountId, ChargerSessionCreated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                transaction_id, company_id, site_id, charger_id,
                connector_id, driver_id, id_tag, timestamp,
                "Started", pricing_plan_id, discount_id, now
            )
        )
        
        # Log the pricing information
        pricing_info = f"Pricing Plan ID: {pricing_plan_id}, Discount ID: {discount_id}"
        logger.info(f"✅ CHARGE SESSION CREATED: ID {transaction_id} for charger {charger_id}, connector {connector_id} | {pricing_info}")
        
        return transaction_id
        
    except Exception as e:
        logger.error(f"❌ DATABASE ERROR: Failed to create charge session: {str(e)}")
        return 1  # Default transaction ID

def create_charge_session(charger_info, id_tag, connector_id, timestamp):
    """
    Create a new charge session in the database (backward compatibility).
    
    Args:
        charger_info (dict): Dictionary with charger_id, company_id, site_id
        id_tag (str): The RFID card ID
        connector_id (int): ID of the connector
        timestamp (str): Start time of the session
        
    Returns:
        int: Transaction ID of the new session
    """
    return create_charge_session_with_pricing(charger_info, id_tag, connector_id, timestamp)

def get_charge_session_info(transaction_id):
    """
    Get information about a charge session.
    
    Args:
        transaction_id (int): ID of the charge session
        
    Returns:
        dict: Session information or None if not found
    """
    try:
        session = execute_query(
            """
            SELECT ChargerSessionConnectorId, ChargerSessionStart, ChargerSessionDriverId
            FROM ChargeSessions 
            WHERE ChargeSessionId = ?
            """,
            (transaction_id,)
        )
        
        if session:
            return {
                'connector_id': session[0]["ChargerSessionConnectorId"],
                'start_time': session[0]["ChargerSessionStart"],
                'driver_id': session[0]["ChargerSessionDriverId"]
            }
        else:
            logger.warning(f"⚠️ Transaction {transaction_id} not found in database")
            return None
            
    except Exception as e:
        logger.error(f"❌ DATABASE ERROR: Failed to get session info: {str(e)}")
        return None

def get_meter_start_value(transaction_id):
    """
    Get the meter start value for a transaction.
    
    Args:
        transaction_id (int): ID of the charge session
        
    Returns:
        float: Meter start value or 0 if not found
    """
    try:
        meter_start_event = execute_query(
            """
            SELECT EventsDataMeterValue 
            FROM EventsData 
            WHERE EventsDataSessionId = ? AND EventsDataType = 'StartTransaction'
            ORDER BY EventsDataDateTime ASC LIMIT 1
            """,
            (transaction_id,)
        )
        
        if meter_start_event and meter_start_event[0]["EventsDataMeterValue"] is not None:
            return meter_start_event[0]["EventsDataMeterValue"]
        else:
            return 0
            
    except Exception as e:
        logger.error(f"❌ DATABASE ERROR: Failed to get meter start value: {str(e)}")
        return 0

def check_rfid_authorization(id_tag, charger_info):
    """
    Check if an RFID card is authorized to use the charger.
    
    Args:
        id_tag (str): The RFID card ID
        charger_info (dict): Dictionary with charger_id, company_id, site_id
        
    Returns:
        str: Authorization status (from ocpp.v16.enums.AuthorizationStatus)
    """
    from ocpp.v16.enums import AuthorizationStatus
    
    try:
        company_id = charger_info['company_id']
        site_id = charger_info['site_id']
        
        # Check if RFID card exists and is enabled
        rfid_card = execute_query(
            "SELECT RFIDCardDriverId, RFIDCardEnabled FROM RFIDCards WHERE RFIDCardId = ?",
            (id_tag,)
        )
        
        if not rfid_card:
            logger.info(f"🚫 Authorization rejected: RFID card {id_tag} not found in database")
            return AuthorizationStatus.invalid
            
        if not rfid_card[0]["RFIDCardEnabled"]:
            logger.info(f"🚫 Authorization rejected: RFID card {id_tag} is blocked")
            return AuthorizationStatus.blocked
                
        driver_id = rfid_card[0]["RFIDCardDriverId"]
            
        # Check if driver is allowed to use chargers at this site
        permission = execute_query(
            """
            SELECT ChargerUsePermitEnabled FROM ChargerUsePermit
            WHERE ChargerUsePermitDriverId = ? AND ChargerUsePermitSiteId = ? AND
                  ChargerUsePermitCompanyId = ?
            """,
            (driver_id, site_id, company_id)
        )
            
        if permission and not permission[0]["ChargerUsePermitEnabled"]:
            logger.info(f"🚫 Authorization rejected: Driver {driver_id} not permitted at site {site_id}")
            return AuthorizationStatus.blocked
        
        logger.info(f"✅ Authorization accepted: RFID card {id_tag} for driver {driver_id}")
        return AuthorizationStatus.accepted
        
    except Exception as e:
        logger.error(f"❌ DATABASE ERROR: Failed to check RFID authorization: {str(e)}")
        return AuthorizationStatus.invalid

def update_charge_session_on_stop(transaction_id, timestamp, duration_seconds, reason, energy_kwh):
    """
    Update a charge session when it stops.
    
    Args:
        transaction_id (int): ID of the charge session
        timestamp (str): End time of the session
        duration_seconds (int): Duration in seconds
        reason (str): Reason for stopping
        energy_kwh (float): Energy used in kWh
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        execute_update(
            """
            UPDATE ChargeSessions
            SET ChargerSessionEnd = ?, ChargerSessionDuration = ?,
                ChargerSessionReason = ?, ChargerSessionStatus = ?,
                ChargerSessionEnergyKWH = ?
            WHERE ChargeSessionId = ?
            """,
            (timestamp, duration_seconds, reason, "Completed", energy_kwh, transaction_id)
        )
        logger.info(f"✅ CHARGE SESSION UPDATED: ID {transaction_id}, duration {duration_seconds}s, energy {energy_kwh} kWh")
        return True
        
    except Exception as e:
        logger.error(f"❌ DATABASE ERROR: Failed to update charge session: {str(e)}")
        return False