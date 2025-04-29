"""
ChargePoint implementation for OCPP 1.6
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
        response = call_result.BootNotification(
            current_time=datetime.now().isoformat(),
            interval=300, 
            status=RegistrationStatus.accepted
        )
        logger.info(f"🔄 RESPONSE: BootNotification.conf with status={RegistrationStatus.accepted}")
        return response

    @on(Action.status_notification)
    def on_status_notification(self, **kwargs):
        logger.info(f"📊 RECEIVED: StatusNotification from {self.id}")
        logger.info(f"📊 DETAILS: connector_id={kwargs.get('connector_id', 'N/A')}, status={kwargs.get('status', 'N/A')}, error_code={kwargs.get('error_code', 'N/A')}")
        return call_result.StatusNotification()

    @on(Action.heartbeat)
    def on_heartbeat(self, **kwargs):
        current_time = datetime.now().isoformat()
        logger.info(f"💓 RECEIVED: Heartbeat from {self.id}")
        logger.info(f"💓 RESPONSE: Heartbeat.conf with current_time={current_time}")
        return call_result.Heartbeat(current_time=current_time)

    @on(Action.authorize)
    def on_authorize(self, **kwargs):
        logger.info(f"🔑 RECEIVED: Authorize from {self.id}")
        logger.info(f"🔑 DETAILS: id_tag={kwargs.get('id_tag', 'N/A')}")
        status = AuthorizationStatus.accepted
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
        transaction_id = 1
        status = AuthorizationStatus.accepted
        logger.info(f"▶️ RESPONSE: StartTransaction.conf with transaction_id={transaction_id}, status={status}")
        id_tag_info = IdTagInfo(status=status)
        return call_result.StartTransaction(
            transaction_id=transaction_id,
            id_tag_info=id_tag_info
        )

    @on(Action.stop_transaction)
    def on_stop_transaction(self, **kwargs):
        logger.info(f"⏹️ RECEIVED: StopTransaction from {self.id}")
        logger.info(f"⏹️ DETAILS: transaction_id={kwargs.get('transaction_id', 'N/A')}, meter_stop={kwargs.get('meter_stop', 'N/A')}, timestamp={kwargs.get('timestamp', 'N/A')}")
        status = AuthorizationStatus.accepted
        logger.info(f"⏹️ RESPONSE: StopTransaction.conf with status={status}")
        return call_result.StopTransaction(
            id_tag_info=IdTagInfo(status=status)
        )

    @on(Action.meter_values)
    def on_meter_values(self, **kwargs):
        logger.info(f"📈 RECEIVED: MeterValues from {self.id}")
        logger.info(f"📈 DETAILS: connector_id={kwargs.get('connector_id', 'N/A')}, transaction_id={kwargs.get('transaction_id', 'N/A')}")
        
        # Log meter values in detail if available
        if 'meter_value' in kwargs:
            for meter_val in kwargs['meter_value']:
                timestamp = meter_val.get('timestamp', 'N/A')
                for sample in meter_val.get('sampled_value', []):
                    value = sample.get('value', 'N/A')
                    unit = sample.get('unit', 'N/A')
                    measurand = sample.get('measurand', 'N/A')
                    logger.info(f"📈 METER READING: {value} {unit} ({measurand}) at {timestamp}")
        
        logger.info(f"📈 RESPONSE: MeterValues.conf")
        return call_result.MeterValues()

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