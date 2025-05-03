"""
Refactored ChargePoint implementation for OCPP 1.6
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
    create_charge_session,
    update_charge_session_on_stop,
    get_charge_session_info,
    get_meter_start_value,
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
    ChargePoint implementation for OCPP 1.6
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
            
            # Get charger info for logging event
            # Dont need to log BootNotification in EventsData
            #charger_info = get_charger_info(self.id)
            # if charger_info:
            #     # Log boot notification event
            #     log_event(
            #         charger_info,
            #         event_type="BootNotification",
            #         data=kwargs,
            #         connector_id=None,
            #         session_id=None
            #     )
                
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
            #now = datetime.now().isoformat() # Time for reporting connector status
            connector_id = kwargs.get('connector_id') 
            status = kwargs.get('status') # Only need to update connector status
            
            # Get charger info from database
            charger_info = get_charger_info(self.id)
            if not charger_info:
                logger.error(f"❌ Charger {self.id} not found in database")
                return call_result.StatusNotification()
            
            # Update connector status if connector_id is provided and not 0
            if connector_id is not None and connector_id != 0:
                update_connector_status(charger_info, connector_id, status)
            
            # Log status notification event
            # Dont need to log status notification in EventsData table in database
            # log_event(
            #     charger_info, 
            #     event_type="StatusNotification", 
            #     data=kwargs,
            #     connector_id=connector_id,
            #     session_id=None
            # )
            
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
            if not charger_info:
                logger.error(f"❌ Charger {self.id} not found in database")
                return call_result.MeterValues()
            
            # Log meter values in detail if available
            if 'meter_value' in kwargs:
                for meter_val in kwargs['meter_value']:
                    timestamp = meter_val.get('timestamp', now)
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
                            
                            # Store in appropriate field based on measurand
                            if measurand == 'Energy.Active.Import.Register' or measurand == 'Energy.Active.Import.Interval':
                                meter_data['meter_value'] = parsed_value
                            elif measurand == 'Current.Import':
                                meter_data['current'] = parsed_value
                            elif measurand == 'Voltage':
                                meter_data['voltage'] = parsed_value
                            elif measurand == 'Temperature':
                                meter_data['temperature'] = parsed_value
                            else:
                                # Default to meter value for other measurands
                                meter_data['meter_value'] = parsed_value
                            
                            # Log meter values event
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
            
            # Default authorization status
            authorization_status = AuthorizationStatus.accepted
            
            # Get charger info from database
            charger_info = get_charger_info(self.id)
            if not charger_info:
                logger.error(f"❌ Charger {self.id} not found in database")
                return call_result.Authorize(id_tag_info=IdTagInfo(status=authorization_status))
            
            # Check if RFID card is authorized
            if id_tag:
                authorization_status = check_rfid_authorization(id_tag, charger_info)
            
            # Log authorization event
            log_event(
                charger_info,
                event_type="Authorize",
                data={"id_tag": id_tag, "status": authorization_status},
                connector_id=None,
                session_id=None
            )
            logger.info(f"✅ EVENT LOGGED: Authorization for {self.id}, RFID {id_tag}, status {authorization_status}")
            
        except Exception as e:
            logger.error(f"❌ DATABASE ERROR: Failed to process authorization for {self.id}: {str(e)}")
            # Default to accepted if there's a database error
            authorization_status = AuthorizationStatus.accepted
        
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
        
        # Handle start transaction in database
        try:
            now = datetime.now().isoformat()
            id_tag = kwargs.get('id_tag')
            connector_id = kwargs.get('connector_id')
            meter_start = kwargs.get('meter_start', 0)
            timestamp = kwargs.get('timestamp', now)
            
            # Default response values
            transaction_id = 1
            status = AuthorizationStatus.accepted
            
            # Get charger info from database
            charger_info = get_charger_info(self.id)
            if not charger_info:
                logger.error(f"❌ Charger {self.id} not found in database")
                return call_result.StartTransaction(transaction_id=transaction_id, id_tag_info=IdTagInfo(status=status))
            
            # Create new charge session and get transaction ID
            transaction_id = create_charge_session(charger_info, id_tag, connector_id, timestamp)
            
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
            transaction_id = 1
            status = AuthorizationStatus.accepted
        
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
        
        # Handle stop transaction in database
        try:
            now = datetime.now().isoformat()
            transaction_id = kwargs.get('transaction_id')
            meter_stop = kwargs.get('meter_stop', 0)
            timestamp = kwargs.get('timestamp', now)
            reason = kwargs.get('reason')
            
            # Default response value
            status = AuthorizationStatus.accepted
            
            # Get charger info from database
            charger_info = get_charger_info(self.id)
            if not charger_info:
                logger.error(f"❌ Charger {self.id} not found in database")
                return call_result.StopTransaction(id_tag_info=IdTagInfo(status=status))
            
            # Get session info
            session_info = get_charge_session_info(transaction_id)
            
            if session_info:
                connector_id = session_info.get('connector_id')
                start_time = session_info.get('start_time')
                
                # Calculate duration and energy
                try:
                    # Calculate duration
                    start_dt = datetime.fromisoformat(start_time)
                    end_dt = datetime.fromisoformat(timestamp)
                    duration_seconds = int((end_dt - start_dt).total_seconds())
                    
                    # Get meter start value
                    meter_start = get_meter_start_value(transaction_id)
                    
                    # Calculate energy used in kWh
                    energy_kwh = (meter_stop - meter_start) / 1000.0  # Convert from Wh to kWh
                    
                    # Update session record
                    update_charge_session_on_stop(
                        transaction_id, 
                        timestamp, 
                        duration_seconds, 
                        reason, 
                        energy_kwh
                    )
                    logger.info(f"✅ CHARGE SESSION UPDATED: ID {transaction_id} for charger {self.id}, duration {duration_seconds}s, energy {energy_kwh} kWh")
                    
                    # Update connector status to Available
                    if connector_id is not None:
                        update_connector_status(charger_info, connector_id, 'Available')
                        
                except Exception as e:
                    logger.error(f"❌ Error updating session: {str(e)}")
            else:
                logger.warning(f"⚠️ Transaction {transaction_id} not found in database")
            
            # Log stop transaction event with meter stop value
            log_event(
                charger_info,
                event_type="StopTransaction",
                data=kwargs,
                connector_id=None,  # We don't have connector_id directly from kwargs
                session_id=transaction_id,
                timestamp=timestamp,
                meter_value=meter_stop
            )
            logger.info(f"✅ EVENT LOGGED: Stop transaction for {self.id}, transaction {transaction_id}, meter {meter_stop}")
            
        except Exception as e:
            logger.error(f"❌ DATABASE ERROR: Failed to process stop transaction for {self.id}: {str(e)}")
            # Default value if database error
            status = AuthorizationStatus.accepted
        
        logger.info(f"⏹️ RESPONSE: StopTransaction.conf with status={status}")
        return call_result.StopTransaction(
            id_tag_info=IdTagInfo(status=status)
        )

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