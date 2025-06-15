"""
Enhanced ChargePoint implementation for OCPP 1.6 with improved payment handling
"""
import logging
from datetime import datetime
import sys
from pathlib import Path
import json

from ocpp.routing import on
from ocpp.v16 import ChargePoint as cp
from ocpp.v16 import call, call_result
from ocpp.v16.datatypes import IdTagInfo
from ocpp.v16.enums import (
    Action,
    RegistrationStatus,
    AuthorizationStatus,
    ConfigurationStatus,
    TriggerMessageStatus,
    ClearCacheStatus,
    ResetStatus,
    UnlockStatus,
    AvailabilityStatus,
    RemoteStartStopStatus,
    ChargingProfileStatus,
    ReservationStatus,
    CancelReservationStatus,
    UpdateStatus,
    DataTransferStatus,
    CertificateSignedStatus,
    DeleteCertificateStatus,
    CertificateStatus,
    GetInstalledCertificateStatus,
    LogStatus,
    GenericStatus
)

# Import database functions
from app.db.database import execute_query, execute_update, execute_insert
from app.db.charge_point_db import (
    update_charger_on_boot,
    log_event,
    update_charger_heartbeat,
    update_connector_status,
    get_charger_info,
    check_rfid_authorization,
    create_charge_session_with_pricing_and_payment,
    create_payment_transaction_for_start,
    update_existing_payment_transaction,
    get_charge_session_info,
    get_meter_start_value,
    get_default_payment_method,
    
)

def setup_logger(logger_name):
    """Set up a logger instance."""
    logger = logging.getLogger(logger_name)
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger

# Set up logging
logger = setup_logger("ocpp_charge_point")

class ChargePoint16(cp):
    """
    Enhanced ChargePoint implementation for OCPP 1.6 with improved payment handling
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.id = args[0] if args else "unknown"
        logger.info(f"📱 Initializing ChargePoint: {self.id}")

    @on(Action.boot_notification)
    def on_boot_notification(self, **kwargs):
        logger.info(f"🔌 RECEIVED: BootNotification from {self.id}")
        logger.info(f"🔌 DETAILS: {json.dumps(kwargs)}")
        
        # Update the database with boot notification details
        try:
            # Extract relevant fields from boot notification
            charger_details = {
                'charger_brand': kwargs.get('charge_point_vendor'),
                'charger_model': kwargs.get('charge_point_model'),
                'charger_serial': kwargs.get('charge_point_serial_number'),
                'firmware_version': kwargs.get('firmware_version'),
                'charger_meter_serial': kwargs.get('meter_serial_number'),
                'charger_meter': kwargs.get('meter_type'),
            }
            
            # Update charger details in database
            update_charger_on_boot(self.id, charger_details)
            
        except Exception as e:
            logger.error(f"❌ DATABASE ERROR: Failed to update boot notification details for {self.id}: {str(e)}")
        
        # Send response to charger
        response = call_result.BootNotification(
            current_time=datetime.now().isoformat(),
            interval=300, 
            status=RegistrationStatus.accepted
        )
        logger.info(f"🔄 RESPONSE: BootNotification.conf with status={RegistrationStatus.accepted}")
        return response

    @on(Action.heartbeat)
    def on_heartbeat(self, **kwargs):
        current_time = datetime.now().isoformat()
        logger.info(f"💓 RECEIVED: Heartbeat from {self.id}")
        
        # Update the database with heartbeat information
        try:
            update_charger_heartbeat(self.id, current_time)
            logger.info(f"✅ DATABASE UPDATED: Heartbeat for {self.id} at {current_time}")
        except Exception as e:
            logger.error(f"❌ DATABASE ERROR: Failed to update heartbeat for {self.id}: {str(e)}")
                
        logger.info(f"💓 RESPONSE: Heartbeat.conf with current_time={current_time}")
        return call_result.Heartbeat(current_time=current_time)

    @on(Action.status_notification)
    def on_status_notification(self, **kwargs):
        logger.info(f"📊 RECEIVED: StatusNotification from {self.id}")
        logger.info(f"📊 DETAILS: connector_id={kwargs.get('connector_id', 'N/A')}, status={kwargs.get('status', 'N/A')}, error_code={kwargs.get('error_code', 'N/A')}")
        
        try:
            connector_id = kwargs.get('connector_id') 
            status = kwargs.get('status')
            
            # Get charger info from database
            charger_info = get_charger_info(self.id)
            if not charger_info:
                logger.error(f"❌ Charger {self.id} not found in database")
                return call_result.StatusNotification()
            
            # Update connector status if connector_id is provided and not 0
            if connector_id is not None and connector_id != 0:
                update_connector_status(charger_info, connector_id, status)
            
        except Exception as e:
            logger.error(f"❌ DATABASE ERROR: Failed to update status for {self.id}: {str(e)}")
        
        return call_result.StatusNotification()

    @on(Action.meter_values)
    def on_meter_values(self, **kwargs):
        logger.info(f"📈 RECEIVED: MeterValues from {self.id}")
        logger.info(f"📈 DETAILS: connector_id={kwargs.get('connector_id', 'N/A')}, transaction_id={kwargs.get('transaction_id', 'N/A')}")
        
        try:
            now = datetime.now().isoformat()
            connector_id = kwargs.get('connector_id')
            transaction_id = kwargs.get('transaction_id')
            
            # Get charger info from database
            charger_info = get_charger_info(self.id)
            
            # Process meter values in detail
            if 'meter_value' in kwargs:
                for meter_val in kwargs['meter_value']:
                    timestamp = meter_val.get('timestamp', now)
                    
                    # Check for active session if no transaction_id provided
                    if transaction_id is None and connector_id is not None:
                        # Get active session for this connector
                        active_session = execute_query(
                            """
                            SELECT ChargeSessionId FROM ChargeSessions 
                            WHERE ChargerSessionChargerId = ? AND ChargerSessionCompanyId = ? 
                            AND ChargerSessionSiteId = ? AND ChargerSessionConnectorId = ?
                            AND ChargerSessionEnd IS NULL
                            """,
                            (charger_info['charger_id'], charger_info['company_id'], charger_info['site_id'], connector_id)
                        )
                        
                        if active_session:
                            transaction_id = active_session[0]["ChargeSessionId"]
                            logger.info(f"📊 Found active session {transaction_id} for connector {connector_id}")
                    
                    for sample in meter_val.get('sampled_value', []):
                        value = sample.get('value', 'N/A')
                        unit = sample.get('unit', 'N/A')
                        measurand = sample.get('measurand', 'N/A')
                        logger.info(f"📈 METER READING: {value} {unit} ({measurand}) at {timestamp}")
                        
                        # Parse value as float if possible
                        try:
                            parsed_value = float(value)
                            
                            # Prepare meter data
                            meter_data = {
                                'timestamp': timestamp,
                                'sample': sample,
                                'meter_value': None,
                                'current': None,
                                'voltage': None,
                                'temperature': None
                            }
                            
                            # Only store in meter_value if it's specifically Energy.Active.Import.Register
                            if measurand == 'Energy.Active.Import.Register':
                                meter_data['meter_value'] = parsed_value
                                
                                # Update session energy if this is an active session
                                if transaction_id:
                                    try:
                                        # Get the session
                                        session = execute_query(
                                            "SELECT ChargerSessionStart FROM ChargeSessions WHERE ChargeSessionId = ?",
                                            (transaction_id,)
                                        )
                                        
                                        if session:
                                            # Calculate running energy for live update
                                            start_meter = get_meter_start_value(transaction_id)
                                            current_energy = (parsed_value - start_meter) / 1000.0  # Wh to kWh
                                            
                                            if current_energy > 0:
                                                # Update running energy in session
                                                execute_update(
                                                    """
                                                    UPDATE ChargeSessions 
                                                    SET ChargerSessionEnergyKWH = ? 
                                                    WHERE ChargeSessionId = ?
                                                    """,
                                                    (current_energy, transaction_id)
                                                )
                                                logger.info(f"✅ Updated session {transaction_id} with energy {current_energy} kWh")
                                    except Exception as e:
                                        logger.error(f"❌ Error updating session energy: {str(e)}")
                            elif measurand == 'Current.Import':
                                meter_data['current'] = parsed_value
                            elif measurand == 'Voltage':
                                meter_data['voltage'] = parsed_value
                            elif measurand == 'Temperature':
                                meter_data['temperature'] = parsed_value
                            else:
                                logger.info(f"📊 Other measurand received: {measurand}, value: {parsed_value}")
                            
                            # Log only energy readings to EventsDataMeterValue
                            log_event(
                                charger_info,
                                event_type="MeterValues",
                                data=meter_data,
                                connector_id=connector_id,
                                session_id=transaction_id,
                                timestamp=timestamp,
                                meter_value=meter_data['meter_value'],
                                temperature=meter_data['temperature'],
                                current=meter_data['current'],
                                voltage=meter_data['voltage']
                            )
                            logger.info(f"✅ METER VALUE LOGGED: {self.id}, connector {connector_id}, value {value} {unit}")
                            
                        except (ValueError, TypeError):
                            # If value cannot be parsed as float, just log it in the data field
                            log_event(
                                charger_info,
                                event_type="MeterValues",
                                data=sample,
                                connector_id=connector_id,
                                session_id=transaction_id,
                                timestamp=timestamp
                            )
                            
        except Exception as e:
            logger.error(f"❌ DATABASE ERROR: Failed to process meter values for {self.id}: {str(e)}")
        
        logger.info(f"📈 RESPONSE: MeterValues.conf")
        return call_result.MeterValues()
   
    @on(Action.authorize)
    def on_authorize(self, **kwargs):
        logger.info(f"🔑 RECEIVED: Authorize from {self.id}")
        logger.info(f"🔑 DETAILS: id_tag={kwargs.get('id_tag', 'N/A')}")
        
        # Handle authorization against database
        try:
            id_tag = kwargs.get('id_tag')
            now = datetime.now().isoformat()
            
            # Default authorization status is invalid
            authorization_status = AuthorizationStatus.invalid
            
            # Get charger info from database
            charger_info = get_charger_info(self.id)
            if not charger_info:
                logger.error(f"❌ Charger {self.id} not found in database")
                return call_result.Authorize(id_tag_info=IdTagInfo(status=authorization_status))
            
            # Check if RFID card exists in database
            if id_tag:
                # Query the database for the RFID card
                rfid_card = execute_query(
                    "SELECT RFIDCardId, RFIDCardEnabled FROM RFIDCards WHERE RFIDCardId = ?",
                    (id_tag,)
                )
                
                if rfid_card:
                    # RFID card exists in database
                    if rfid_card[0]["RFIDCardEnabled"]:
                        # RFID card is enabled, check for additional permissions
                        authorization_status = check_rfid_authorization(id_tag, charger_info)
                    else:
                        # RFID card is disabled
                        authorization_status = AuthorizationStatus.blocked
                        logger.info(f"🚫 Authorization rejected: RFID card {id_tag} is blocked")
                else:
                    # RFID card not found in database
                    authorization_status = AuthorizationStatus.invalid
                    logger.info(f"🚫 Authorization rejected: RFID card {id_tag} not in database")
            else:
                # No ID tag provided
                authorization_status = AuthorizationStatus.invalid
                logger.info(f"🚫 Authorization rejected: No RFID card ID provided")
            
            logger.info(f"✅ EVENT LOGGED: Authorization for {self.id}, RFID {id_tag}, status {authorization_status}")
            
        except Exception as e:
            logger.error(f"❌ DATABASE ERROR: Failed to process authorization for {self.id}: {str(e)}")
            # Default to rejected if there's a database error
            authorization_status = AuthorizationStatus.invalid
        
        status = authorization_status
        logger.info(f"🔑 RESPONSE: Authorize.conf with status={status}")
        return call_result.Authorize(
            id_tag_info=IdTagInfo(
                status=status
            )
        )

    @on(Action.start_transaction)
    def on_start_transaction(self, **kwargs):
        logger.info(f"▶️ RECEIVED: StartTransaction from {self.id}")
        logger.info(f"▶️ DETAILS: id_tag={kwargs.get('id_tag', 'N/A')}, connector_id={kwargs.get('connector_id', 'N/A')}, meter_start={kwargs.get('meter_start', 'N/A')}")
        
        try:
            now = datetime.now().isoformat()
            id_tag = kwargs.get('id_tag')
            connector_id = kwargs.get('connector_id')
            meter_start = kwargs.get('meter_start', 0)
            timestamp = kwargs.get('timestamp', now)
            
            # Get charger info from database
            charger_info = get_charger_info(self.id)
            status = check_rfid_authorization(id_tag=id_tag, charger_info=charger_info)

            # If authorization failed, reject the transaction
            if status != AuthorizationStatus.accepted:
                logger.warning(f"⚠️ Authorization failed for {id_tag} on {self.id}: {status}")
                return call_result.StartTransaction(
                    transaction_id=0,  # 0 indicates rejection
                    id_tag_info=IdTagInfo(status=status)
                )

            # Find driver ID and pricing information from RFID card
            driver_id = None
            pricing_plan_id = None
            discount_id = None
            payment_transaction_id = None
            
            if id_tag:
                # Get driver and pricing information in one query
                driver_pricing = execute_query(
                    """
                    SELECT 
                        r.RFIDCardDriverId as driver_id,
                        dg.DriverTariffId as pricing_plan_id,
                        dg.DriversGroupDiscountId as discount_id,
                        dg.DriversGroupName as group_name,
                        r.RFIDCardCompanyId as company_id
                    FROM RFIDCards r
                    INNER JOIN Drivers d ON r.RFIDCardDriverId = d.DriverId
                    LEFT JOIN DriversGroup dg ON d.DriverGroupId = dg.DriversGroupId
                    WHERE r.RFIDCardId = ? AND r.RFIDCardEnabled = 1 AND d.DriverEnabled = 1
                    """,
                    (id_tag,)
                )
                
                if driver_pricing:
                    pricing_data = driver_pricing[0]
                    driver_id = pricing_data["driver_id"]
                    pricing_plan_id = pricing_data["pricing_plan_id"]
                    discount_id = pricing_data["discount_id"]
                    company_id = pricing_data["company_id"]
                    
                    logger.info(f"✅ DRIVER FOUND: Driver ID {driver_id} in group '{pricing_data['group_name']}'")
                    logger.info(f"💰 PRICING INFO: Tariff ID: {pricing_plan_id}, Discount ID: {discount_id}")
                    
                    # ENHANCED: Payment method validation and transaction creation
                    if pricing_plan_id:
                        # 1. Check if driver/company has valid payment method
                        payment_method = get_default_payment_method(company_id)
                        
                        if not payment_method:
                            logger.warning(f"⚠️ No payment method found for company {company_id}")
                            # Reject transaction if payment method is required but not found
                            return call_result.StartTransaction(
                                transaction_id=0,
                                id_tag_info=IdTagInfo(status=AuthorizationStatus.invalid)
                            )
                        
                        # 2. Create payment transaction record (pending completion)
                        try:
                            payment_transaction_id = create_payment_transaction_for_start(
                                driver_id=driver_id,
                                company_id=company_id,
                                site_id=charger_info['site_id'],
                                charger_id=charger_info['charger_id'],
                                payment_method_id=payment_method,
                                estimated_amount=0.00,  # Will be calculated at stop
                                status="pending_completion"
                            )
                            
                            if not payment_transaction_id:
                                logger.error(f"❌ Failed to create payment transaction for driver {driver_id}")
                                return call_result.StartTransaction(
                                    transaction_id=0,
                                    id_tag_info=IdTagInfo(status=AuthorizationStatus.invalid)
                                )
                            
                            logger.info(f"✅ Payment transaction created: ID {payment_transaction_id}")
                            
                        except Exception as e:
                            logger.error(f"❌ Error creating payment transaction: {str(e)}")
                            return call_result.StartTransaction(
                                transaction_id=0,
                                id_tag_info=IdTagInfo(status=AuthorizationStatus.invalid)
                            )
                else:
                    logger.warning(f"⚠️ RFID card {id_tag} not found or driver/group disabled")
            
            # Create new charge session with pricing and payment information
            transaction_id = create_charge_session_with_pricing_and_payment(
                charger_info, 
                id_tag, 
                connector_id, 
                timestamp, 
                driver_id,
                pricing_plan_id,
                discount_id,
                payment_transaction_id
            )
            
            # Update connector status to Charging
            if connector_id is not None:
                update_connector_status(charger_info, connector_id, 'Charging')
            
            # Log start transaction event with meter start value
            log_event(
                charger_info,
                event_type="StartTransaction",
                data=kwargs,
                connector_id=connector_id,
                session_id=transaction_id,
                timestamp=timestamp,
                meter_value=meter_start
            )
            logger.info(f"✅ EVENT LOGGED: Start transaction for {self.id}, connector {connector_id}, meter {meter_start}")
            
        except Exception as e:
            logger.error(f"❌ DATABASE ERROR: Failed to process start transaction for {self.id}: {str(e)}")
            # Default values if database error
            transaction_id = 0  # Reject on error
            status = AuthorizationStatus.invalid
        
        id_tag_info = IdTagInfo(status=status)
        logger.info(f"▶️ RESPONSE: StartTransaction.conf with transaction_id={transaction_id}, status={status}")
        return call_result.StartTransaction(
            transaction_id=transaction_id,
            id_tag_info=id_tag_info
        )

    @on(Action.stop_transaction)
    def on_stop_transaction(self, **kwargs):
        logger.info(f"⏹️ RECEIVED: StopTransaction from {self.id}")
        logger.info(f"⏹️ DETAILS: transaction_id={kwargs.get('transaction_id', 'N/A')}, meter_stop={kwargs.get('meter_stop', 'N/A')}, timestamp={kwargs.get('timestamp', 'N/A')}")
        
        try:
            now = datetime.now().isoformat()
            transaction_id = kwargs.get('transaction_id')
            meter_stop = kwargs.get('meter_stop', 0)
            timestamp = kwargs.get('timestamp', now)
            reason = kwargs.get('reason')
            
            # Default response value
            status = AuthorizationStatus.accepted
            
            # Get charger info directly
            charger_info = get_charger_info(self.id)
            
            # Get session info
            session_info = get_charge_session_info(transaction_id)
            
            if session_info:
                connector_id = session_info.get('connector_id')
                start_time = session_info.get('start_time')
                
                # Calculate duration and energy
                try:
                    # Fix for timestamp format issue - handle 'Z' timezone indicator
                    start_time_clean = start_time.replace('Z', '+00:00') if start_time and start_time.endswith('Z') else start_time
                    timestamp_clean = timestamp.replace('Z', '+00:00') if timestamp and timestamp.endswith('Z') else timestamp
                    
                    logger.info(f"🕒 Cleaned timestamps - Start: {start_time_clean}, End: {timestamp_clean}")
                    
                    # Calculate duration
                    start_dt = datetime.fromisoformat(start_time_clean)
                    end_dt = datetime.fromisoformat(timestamp_clean)
                    duration_seconds = int((end_dt - start_dt).total_seconds())
                    
                    # Get meter start value
                    meter_start = get_meter_start_value(transaction_id)
                    
                    # Calculate energy used in kWh
                    energy_kwh = (meter_stop - meter_start) / 1000.0  # Convert from Wh to kWh
                    
                    # SIMPLIFIED: Update existing payment transaction with final cost
                    update_success = update_existing_payment_transaction(
                        transaction_id, 
                        timestamp_clean,
                        duration_seconds, 
                        reason, 
                        energy_kwh
                    )
                    
                    if update_success:
                        logger.info(f"✅ CHARGE SESSION UPDATED: ID {transaction_id} for charger {self.id}")
                    else:
                        logger.error(f"❌ Failed to update charge session")
                    
                    # Update connector status to Available
                    if connector_id is not None:
                        update_connector_status(charger_info, connector_id, 'Available')
                        
                except Exception as e:
                    logger.error(f"❌ Error updating session: {str(e)}")
                    logger.error(f"❌ Debug info - Start time: '{start_time}', End time: '{timestamp}'")
            else:
                logger.warning(f"⚠️ Transaction {transaction_id} not found in database")
            
            # Log stop transaction event with meter stop value
            log_event(
                charger_info,
                event_type="StopTransaction",
                data=kwargs,
                connector_id=None,
                session_id=transaction_id,
                timestamp=timestamp,
                meter_value=meter_stop
            )
            logger.info(f"✅ EVENT LOGGED: Stop transaction for {self.id}, transaction {transaction_id}, meter {meter_stop}")
            
        except Exception as e:
            logger.error(f"❌ DATABASE ERROR: Failed to process stop transaction for {self.id}: {str(e)}")
            logger.error(f"❌ Exception details: {type(e).__name__}, {e.args}")
            status = AuthorizationStatus.accepted
        
        logger.info(f"⏹️ RESPONSE: StopTransaction.conf with status={status}")
        return call_result.StopTransaction(
            id_tag_info=IdTagInfo(status=status)
        )
    
    # OCPP Remote Commands
    async def change_configuration_req(self, key, value):
        logger.info(f"⚙️ SENDING: ChangeConfiguration to {self.id}")
        logger.info(f"⚙️ DETAILS: key={key}, value={value}")
        payload = call.ChangeConfiguration(key=key, value=value)
        response = await self.call(payload)
        logger.info(f"⚙️ RECEIVED RESPONSE: ChangeConfiguration.conf with status={response.status}")
        return response

    async def reset_req(self, type):
        logger.info(f"🔄 SENDING: Reset to {self.id}")
        logger.info(f"🔄 DETAILS: type={type}")
        payload = call.Reset(type=type)
        response = await self.call(payload)
        logger.info(f"🔄 RECEIVED RESPONSE: Reset.conf with status={response.status}")
        return response

    async def unlock_connector_req(self, connector_id):
        logger.info(f"🔓 SENDING: UnlockConnector to {self.id}")
        logger.info(f"🔓 DETAILS: connector_id={connector_id}")
        payload = call.UnlockConnector(connector_id=connector_id)
        response = await self.call(payload)
        logger.info(f"🔓 RECEIVED RESPONSE: UnlockConnector.conf with status={response.status}")
        return response

    async def get_configuration_req(self, key=None):
        logger.info(f"🔍 SENDING: GetConfiguration to {self.id}")
        logger.info(f"🔍 DETAILS: key={key}")
        payload = call.GetConfiguration(key=key)
        response = await self.call(payload)
        logger.info(f"🔍 RECEIVED RESPONSE: GetConfiguration.conf with {len(getattr(response, 'configuration_key', []))} configuration keys")
        return response

    async def change_availability_req(self, connector_id, type):
        logger.info(f"🔌 SENDING: ChangeAvailability to {self.id}")
        logger.info(f"🔌 DETAILS: connector_id={connector_id}, type={type}")
        payload = call.ChangeAvailability(connector_id=connector_id, type=type)
        response = await self.call(payload)
        logger.info(f"🔌 RECEIVED RESPONSE: ChangeAvailability.conf with status={response.status}")
        return response

    async def remote_start_transaction_req(self, id_tag, connector_id=None, charging_profile=None):
        logger.info(f"▶️ SENDING: RemoteStartTransaction to {self.id}")
        logger.info(f"▶️ DETAILS: id_tag={id_tag}, connector_id={connector_id}")
        payload = call.RemoteStartTransaction(
            id_tag=id_tag,
            connector_id=connector_id,
            charging_profile=charging_profile
        )
        response = await self.call(payload)
        logger.info(f"▶️ RECEIVED RESPONSE: RemoteStartTransaction.conf with status={response.status}")
        return response

    async def remote_stop_transaction_req(self, transaction_id):
        logger.info(f"⏹️ SENDING: RemoteStopTransaction to {self.id}")
        logger.info(f"⏹️ DETAILS: transaction_id={transaction_id}")
        payload = call.RemoteStopTransaction(transaction_id=transaction_id)
        response = await self.call(payload)
        logger.info(f"⏹️ RECEIVED RESPONSE: RemoteStopTransaction.conf with status={response.status}")
        return response

    async def set_charging_profile_req(self, connector_id, cs_charging_profiles):
        logger.info(f"📋 SENDING: SetChargingProfile to {self.id}")
        logger.info(f"📋 DETAILS: connector_id={connector_id}, profile={json.dumps(cs_charging_profiles)}")
        payload = call.SetChargingProfile(
            connector_id=connector_id,
            cs_charging_profiles=cs_charging_profiles
        )
        response = await self.call(payload)
        logger.info(f"📋 RECEIVED RESPONSE: SetChargingProfile.conf with status={response.status}")
        return response

    async def reserve_now_req(self, connector_id, expiry_date, id_tag, reservation_id, parent_id_tag=None):
        logger.info(f"🔖 SENDING: ReserveNow to {self.id}")
        logger.info(f"🔖 DETAILS: connector_id={connector_id}, expiry_date={expiry_date}, id_tag={id_tag}, reservation_id={reservation_id}")
        payload = call.ReserveNow(
            connector_id=connector_id,
            expiry_date=expiry_date,
            id_tag=id_tag,
            reservation_id=reservation_id,
            parent_id_tag=parent_id_tag
        )
        response = await self.call(payload)
        logger.info(f"🔖 RECEIVED RESPONSE: ReserveNow.conf with status={response.status}")
        return response

    async def cancel_reservation_req(self, reservation_id):
        logger.info(f"❌ SENDING: CancelReservation to {self.id}")
        logger.info(f"❌ DETAILS: reservation_id={reservation_id}")
        payload = call.CancelReservation(reservation_id=reservation_id)
        response = await self.call(payload)
        logger.info(f"❌ RECEIVED RESPONSE: CancelReservation.conf with status={response.status}")
        return response
