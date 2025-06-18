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

# Add these functions to app/db/charge_point_db.py

def update_charge_session_on_stop_with_payment(transaction_id, timestamp, duration_seconds, reason, energy_kwh):
    """
    Enhanced version that calculates cost and creates payment transaction.
    
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
        # 1. Get session details including pricing info
        session = execute_query(
            """
            SELECT ChargerSessionPricingPlanId, ChargerSessionStart, 
                   ChargerSessionCompanyId, ChargerSessionSiteId,
                   ChargerSessionChargerId, ChargerSessionDriverId
            FROM ChargeSessions WHERE ChargeSessionId = ?
            """,
            (transaction_id,)
        )
        
        if not session:
            logger.error(f"Session {transaction_id} not found for payment calculation")
            return False
            
        session_data = session[0]
        
        # 2. Calculate cost using TariffService
        cost = 0.0
        breakdown = {}
        
        if session_data["ChargerSessionPricingPlanId"] and energy_kwh > 0:
            from app.services.tariff_service import TariffService
            cost, breakdown = TariffService.calculate_session_cost(
                pricing_plan_id=session_data["ChargerSessionPricingPlanId"],
                energy_kwh=energy_kwh,
                session_start=session_data["ChargerSessionStart"],
                session_end=timestamp
            )
            logger.info(f"Session {transaction_id} cost calculated: ${cost:.2f}")
        else:
            logger.info(f"Session {transaction_id} - no pricing plan or zero energy, cost = $0.00")
        
        # 3. Create payment transaction if cost > 0
        payment_transaction_id = None
        payment_status = "not_required"
        
        if cost > 0:
            payment_transaction_id = create_payment_transaction_for_session(
                session_data, transaction_id, cost
            )
            payment_status = "pending" if payment_transaction_id else "failed"
            logger.info(f"Payment transaction {payment_transaction_id} created for session {transaction_id}")
        
        # 4. Update session with all fields
        execute_update(
            """
            UPDATE ChargeSessions
            SET ChargerSessionEnd = ?, ChargerSessionDuration = ?,
                ChargerSessionReason = ?, ChargerSessionStatus = ?,
                ChargerSessionEnergyKWH = ?, ChargerSessionCost = ?,
                ChargerSessionPaymentId = ?, ChargerSessionPaymentAmount = ?,
                ChargerSessionPaymentStatus = ?
            WHERE ChargeSessionId = ?
            """,
            (timestamp, duration_seconds, reason, "Completed", energy_kwh, 
             cost, payment_transaction_id, cost, payment_status, transaction_id)
        )
        
        logger.info(f"✅ CHARGE SESSION UPDATED: ID {transaction_id}, duration {duration_seconds}s, energy {energy_kwh} kWh, cost ${cost:.2f}")
        return True
        
    except Exception as e:
        logger.error(f"❌ DATABASE ERROR: Failed to update charge session with payment: {str(e)}")
        return False

def create_payment_transaction_for_session(session_data, session_id, amount):
    """
    Create payment transaction record for completed session.
    
    Args:
        session_data (dict): Session data from database
        session_id (int): ID of the charge session
        amount (float): Payment amount
        
    Returns:
        int: Payment transaction ID if successful, None otherwise
    """
    try:
        # Get default payment method for the company
        default_payment_method = execute_query(
            """
            SELECT PaymentMethodId FROM PaymentMethods 
            WHERE PaymentMethodCompanyId = ? AND PaymentMethodEnabled = 1
            ORDER BY PaymentMethodId ASC LIMIT 1
            """,
            (session_data["ChargerSessionCompanyId"],)
        )
        
        if not default_payment_method:
            logger.warning(f"No payment method found for company {session_data['ChargerSessionCompanyId']}")
            return None
        
        payment_method_id = default_payment_method[0]["PaymentMethodId"]
        
        # Get maximum transaction ID and increment by 1
        max_id_result = execute_query("SELECT MAX(PaymentTransactionId) as max_id FROM PaymentTransactions")
        new_id = 1
        if max_id_result and max_id_result[0]['max_id'] is not None:
            new_id = max_id_result[0]['max_id'] + 1
            
        now = datetime.now().isoformat()
        
        # Insert new payment transaction
        execute_insert(
            """
            INSERT INTO PaymentTransactions (
                PaymentTransactionId, PaymentTransactionMethodUsed, PaymentTransactionDriverId,
                PaymentTransactionDateTime, PaymentTransactionAmount, PaymentTransactionStatus,
                PaymentTransactionPaymentStatus, PaymentTransactionCompanyId, PaymentTransactionSiteId, 
                PaymentTransactionChargerId, PaymentTransactionSessionId,
                PaymentTransactionCreated, PaymentTransactionUpdated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id,
                payment_method_id,
                session_data["ChargerSessionDriverId"],
                now,
                amount,
                "pending",  
                "pending",    # Payment status - awaiting payment
                session_data["ChargerSessionCompanyId"],
                session_data["ChargerSessionSiteId"],
                session_data["ChargerSessionChargerId"],
                session_id,
                now,
                now
            )
        )
        
        logger.info(f"✅ PAYMENT TRANSACTION CREATED: ID {new_id} for session {session_id}, amount ${amount:.2f}")
        return new_id
        
    except Exception as e:
        logger.error(f"❌ DATABASE ERROR: Failed to create payment transaction: {str(e)}")
        return None

def get_default_payment_method(company_id):
    """
    Get the default payment method for a company.
    
    Args:
        company_id (int): Company ID
        
    Returns:
        int: Payment method ID or None if not found
    """
    try:
        payment_method = execute_query(
            """
            SELECT PaymentMethodId FROM PaymentMethods 
            WHERE PaymentMethodCompanyId = ? AND PaymentMethodEnabled = 1
            ORDER BY PaymentMethodId ASC LIMIT 1
            """,
            (company_id,)
        )
        
        if payment_method:
            return payment_method[0]["PaymentMethodId"]
        else:
            logger.warning(f"No enabled payment method found for company {company_id}")
            return None
            
    except Exception as e:
        logger.error(f"❌ DATABASE ERROR: Failed to get default payment method: {str(e)}")
        return None

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
    


def create_payment_transaction_for_start(driver_id, company_id, site_id, charger_id, payment_method_id, estimated_amount=0.00, status="pending_completion"):
    """
    Create a payment transaction at the start of a charging session.
    
    Args:
        driver_id (int): ID of the driver
        company_id (int): ID of the company
        site_id (int): ID of the site
        charger_id (int): ID of the charger
        payment_method_id (int): ID of the payment method
        estimated_amount (float): Estimated cost (default 0.00)
        status (str): Transaction status
        
    Returns:
        int: Payment transaction ID if successful, None otherwise
    """
    try:
        # Get maximum transaction ID and increment by 1
        max_id_result = execute_query("SELECT MAX(PaymentTransactionId) as max_id FROM PaymentTransactions")
        new_id = 1
        if max_id_result and max_id_result[0]['max_id'] is not None:
            new_id = max_id_result[0]['max_id'] + 1
            
        now = datetime.now().isoformat()
        
        # Insert new payment transaction
        execute_insert(
            """
            INSERT INTO PaymentTransactions (
                PaymentTransactionId, PaymentTransactionMethodUsed, PaymentTransactionDriverId,
                PaymentTransactionDateTime, PaymentTransactionAmount, PaymentTransactionStatus,
                PaymentTransactionPaymentStatus, PaymentTransactionCompanyId, PaymentTransactionSiteId, 
                PaymentTransactionChargerId, PaymentTransactionSessionId,
                PaymentTransactionCreated, PaymentTransactionUpdated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id,
                payment_method_id,
                driver_id,
                now,
                estimated_amount,
                status,
                "pending",  # Payment status - awaiting completion
                company_id,
                site_id,
                charger_id,
                None,  # Session ID will be updated later
                now,
                now
            )
        )
        
        logger.info(f"✅ PAYMENT TRANSACTION CREATED: ID {new_id} for driver {driver_id}, estimated amount ${estimated_amount:.2f}")
        return new_id
        
    except Exception as e:
        logger.error(f"❌ DATABASE ERROR: Failed to create payment transaction: {str(e)}")
        return None


def create_charge_session_with_pricing_and_payment(charger_info, id_tag, connector_id, timestamp, driver_id=None, pricing_plan_id=None, discount_id=None, payment_transaction_id=None):
    """
    Enhanced version of create_charge_session_with_pricing that also links payment transaction.
    
    Args:
        charger_info (dict): Dictionary with charger_id, company_id, site_id
        id_tag (str): The RFID card ID
        connector_id (int): ID of the connector
        timestamp (str): Start time of the session
        driver_id (int, optional): ID of the driver
        pricing_plan_id (int, optional): ID of the pricing plan/tariff
        discount_id (int, optional): ID of the discount
        payment_transaction_id (int, optional): ID of the payment transaction
        
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
        
        # Insert new charge session with pricing and payment information
        execute_insert(
            """
            INSERT INTO ChargeSessions (
                ChargeSessionId, ChargerSessionCompanyId, ChargerSessionSiteId,
                ChargerSessionChargerId, ChargerSessionConnectorId, ChargerSessionDriverId,
                ChargerSessionRFIDCard, ChargerSessionStart, ChargerSessionStatus,
                ChargerSessionPricingPlanId, ChargerSessionDiscountId, ChargerSessionPaymentId,
                ChargerSessionPaymentStatus, ChargerSessionCreated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                transaction_id, company_id, site_id, charger_id,
                connector_id, driver_id, id_tag, timestamp,
                "Started", pricing_plan_id, discount_id, payment_transaction_id,
                "pending" if payment_transaction_id else "not_required", now
            )
        )
        
        # Update payment transaction with session ID
        if payment_transaction_id:
            execute_update(
                """
                UPDATE PaymentTransactions 
                SET PaymentTransactionSessionId = ?, PaymentTransactionUpdated = ?
                WHERE PaymentTransactionId = ?
                """,
                (transaction_id, now, payment_transaction_id)
            )
            logger.info(f"✅ Payment transaction {payment_transaction_id} linked to session {transaction_id}")
        
        # Log the pricing and payment information
        info_parts = []
        if pricing_plan_id:
            info_parts.append(f"Pricing Plan ID: {pricing_plan_id}")
        if discount_id:
            info_parts.append(f"Discount ID: {discount_id}")
        if payment_transaction_id:
            info_parts.append(f"Payment Transaction ID: {payment_transaction_id}")
        
        pricing_info = ", ".join(info_parts) if info_parts else "No pricing/payment info"
        logger.info(f"✅ CHARGE SESSION CREATED: ID {transaction_id} for charger {charger_id}, connector {connector_id} | {pricing_info}")
        
        return transaction_id
        
    except Exception as e:
        logger.error(f"❌ DATABASE ERROR: Failed to create charge session: {str(e)}")
        return 1  # Default transaction ID


def update_existing_payment_transaction(transaction_id, timestamp, duration_seconds, reason, energy_kwh):
    """
    Update existing payment transaction with final cost and complete the session.
    This replaces the complex payment creation logic since payment transaction already exists.
    
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
        # 1. Get session details including existing payment info
        session = execute_query(
            """
            SELECT ChargerSessionPricingPlanId, ChargerSessionStart, 
                   ChargerSessionCompanyId, ChargerSessionSiteId,
                   ChargerSessionChargerId, ChargerSessionDriverId,
                   ChargerSessionPaymentId, ChargerSessionDiscountId
            FROM ChargeSessions WHERE ChargeSessionId = ?
            """,
            (transaction_id,)
        )
        
        if not session:
            logger.error(f"Session {transaction_id} not found")
            return False
            
        session_data = session[0]
        cost = 0.0
        breakdown = {}
        
        # 2. Calculate final cost using TariffService if pricing plan exists
        if session_data["ChargerSessionPricingPlanId"] and energy_kwh > 0:
            from app.services.tariff_service import TariffService
            cost, breakdown = TariffService.calculate_session_cost(
                pricing_plan_id=session_data["ChargerSessionPricingPlanId"],
                energy_kwh=energy_kwh,
                session_start=session_data["ChargerSessionStart"],
                session_end=timestamp
            )
            logger.info(f"Session {transaction_id} final cost calculated: ${cost:.2f}")
        else:
            logger.info(f"Session {transaction_id} - no pricing plan or zero energy, cost = $0.00")
        
        # 3. Update existing payment transaction with final amount
        payment_transaction_id = session_data["ChargerSessionPaymentId"]
        payment_status = "not_required"
        
        if payment_transaction_id and cost > 0:
            now = datetime.now().isoformat()
            execute_update(
                """
                UPDATE PaymentTransactions
                SET PaymentTransactionAmount = ?, PaymentTransactionPaymentStatus = ?, PaymentTransactionUpdated = ?
                WHERE PaymentTransactionId = ?
                """,
                (cost, "pending", now, payment_transaction_id)
            )
            payment_status = "pending"
            logger.info(f"Payment transaction {payment_transaction_id} updated with final amount ${cost:.2f}")
        elif payment_transaction_id and cost == 0:
            # Free session - mark as completed
            now = datetime.now().isoformat()
            execute_update(
                """
                UPDATE PaymentTransactions
                SET PaymentTransactionAmount = ?, PaymentTransactionPaymentStatus = ?, PaymentTransactionUpdated = ?
                WHERE PaymentTransactionId = ?
                """,
                (0.00, "not_required", now, payment_transaction_id)
            )
            payment_status = "not_required"
            logger.info(f"Payment transaction {payment_transaction_id} marked as not required (free session)")
        
        # 4. Update session with final information
        execute_update(
            """
            UPDATE ChargeSessions
            SET ChargerSessionEnd = ?, ChargerSessionDuration = ?,
                ChargerSessionReason = ?, ChargerSessionStatus = ?,
                ChargerSessionEnergyKWH = ?, ChargerSessionCost = ?,
                ChargerSessionPaymentAmount = ?, ChargerSessionPaymentStatus = ?
            WHERE ChargeSessionId = ?
            """,
            (timestamp, duration_seconds, reason, "Completed", energy_kwh, 
             cost, cost, payment_status, transaction_id)
        )
        
        logger.info(f"✅ CHARGE SESSION COMPLETED: ID {transaction_id}, duration {duration_seconds}s, energy {energy_kwh} kWh, cost ${cost:.2f}, payment status: {payment_status}")
        return True
        
    except Exception as e:
        logger.error(f"❌ DATABASE ERROR: Failed to update session with payment: {str(e)}")
        return False

    