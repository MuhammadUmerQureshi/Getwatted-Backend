from fastapi import APIRouter, HTTPException
from app.ws.connection_manager import manager
import logging
import uuid

# Import our new routers
from app.api.company_routes import router as company_router
from app.api.site_routes import router as site_router, company_router as site_company_router
from app.api.charger_routes import router as charger_router, site_router as charger_site_router

router = APIRouter()
logger = logging.getLogger("ocpp.routes")

# Include our new routers
router.include_router(company_router)
router.include_router(site_router)
router.include_router(charger_router)
router.include_router(site_company_router)
router.include_router(charger_site_router)

@router.get("/")
async def root():
    return {"status": "running", "message": "OCPP Server is running"}

@router.get("/charge_points")
async def get_charge_points():
    charge_points = manager.get_charge_points()
    return {"count": len(charge_points), "charge_points": list(charge_points.keys())}

@router.post("/charge_points/{charge_point_id}/reset")
async def reset_charge_point(charge_point_id: str, type: str = "Soft"):
    logger.info(f"🔧 Reset command triggered for {charge_point_id} with type '{type}'")
    
    charge_point = manager.get_charge_points().get(charge_point_id)
    if not charge_point:
        logger.warning(f"⚠️  Charge point '{charge_point_id}' not connected.")
        raise HTTPException(status_code=404, detail=f"Charge point '{charge_point_id}' not connected.")

    try:
        message_id = str(uuid.uuid4())
        ocpp_message = [2, message_id, "Reset", {"type": type}]
        
        logger.info(f"📤 OCPP Message to be sent: {ocpp_message}")
        await charge_point.reset_req(type=type)

        return ocpp_message
    except Exception as e:
        logger.error(f"❌ Reset command failed for {charge_point_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Reset command failed: {str(e)}")

@router.post("/charge_points/{charge_point_id}/change_configuration")
async def change_configuration(charge_point_id: str, key: str, value: str):
    """
    Endpoint to change configuration on a charge point.
    """
    logger.info(f"🛠 Change Configuration command triggered for {charge_point_id} with key '{key}' and value '{value}'")
    
    charge_point = manager.get_charge_points().get(charge_point_id)
    if not charge_point:
        logger.warning(f"⚠️  Charge point '{charge_point_id}' not connected.")
        raise HTTPException(status_code=404, detail=f"Charge point '{charge_point_id}' not connected.")

    try:
        # Send the change configuration request to the charge point
        response = await charge_point.change_configuration_req(key, value)
        
        # Log the response from the charge point
        logger.info(f"📤 OCPP Response from {charge_point_id}: {response.status}")
        
        return {
            "status": "success",
            "charge_point_id": charge_point_id,
            "command": "ChangeConfiguration",
            "key": key,
            "value": value,
            "result": response.status
        }
    
    except Exception as e:
        logger.error(f"❌ Change Configuration command failed for {charge_point_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Change Configuration command failed: {str(e)}")

@router.post("/charge_points/{charge_point_id}/unlock")
async def unlock_connector(charge_point_id: str, connector_id: int):
    logger.info(f"🔓 Unlocking connector {connector_id} on {charge_point_id}")
    cp = manager.get_charge_points().get(charge_point_id)
    if not cp:
        raise HTTPException(status_code=404, detail="Charge point not connected.")
    response = await cp.unlock_connector_req(connector_id)
    return {"command": "UnlockConnector", "connector_id": connector_id, "result": response.status}

@router.get("/charge_points/{charge_point_id}/configuration")
async def get_configuration(charge_point_id: str, key: str = None):
    logger.info(f"📥 Getting configuration for {charge_point_id}, key: {key}")
    cp = manager.get_charge_points().get(charge_point_id)
    if not cp:
        raise HTTPException(status_code=404, detail="Charge point not connected.")
    response = await cp.get_configuration_req(key)
    return response.__dict__

@router.post("/charge_points/{charge_point_id}/availability")
async def change_availability(charge_point_id: str, connector_id: int, type: str):
    logger.info(f"🔄 Changing availability on {charge_point_id} for connector {connector_id} to {type}")
    cp = manager.get_charge_points().get(charge_point_id)
    if not cp:
        raise HTTPException(status_code=404, detail="Charge point not connected.")
    response = await cp.change_availability_req(connector_id, type)
    return {"command": "ChangeAvailability", "result": response.status}

@router.post("/charge_points/{charge_point_id}/remote_start")
async def remote_start_transaction(charge_point_id: str, id_tag: str, connector_id: int = None):
    logger.info(f"⚡ Starting remote transaction on {charge_point_id} with id_tag {id_tag}")
    cp = manager.get_charge_points().get(charge_point_id)
    if not cp:
        raise HTTPException(status_code=404, detail="Charge point not connected.")
    response = await cp.remote_start_transaction_req(id_tag, connector_id)
    return {"command": "RemoteStartTransaction", "result": response.status}

@router.post("/charge_points/{charge_point_id}/remote_stop")
async def remote_stop_transaction(charge_point_id: str, transaction_id: int):
    logger.info(f"🛑 Stopping remote transaction {transaction_id} on {charge_point_id}")
    cp = manager.get_charge_points().get(charge_point_id)
    if not cp:
        raise HTTPException(status_code=404, detail="Charge point not connected.")
    response = await cp.remote_stop_transaction_req(transaction_id)
    return {"command": "RemoteStopTransaction", "transaction_id": transaction_id, "result": response.status}

@router.post("/charge_points/{charge_point_id}/charging_profile")
async def set_charging_profile(charge_point_id: str, connector_id: int, cs_charging_profiles: dict):
    logger.info(f"⚙️ Setting charging profile on {charge_point_id} for connector {connector_id}")
    cp = manager.get_charge_points().get(charge_point_id)
    if not cp:
        raise HTTPException(status_code=404, detail="Charge point not connected.")
    response = await cp.set_charging_profile_req(connector_id, cs_charging_profiles)
    return {"command": "SetChargingProfile", "result": response.status}

@router.post("/charge_points/{charge_point_id}/reserve_now")
async def reserve_now(charge_point_id: str, connector_id: int, expiry_date: str, id_tag: str, reservation_id: int, parent_id_tag: str = None):
    logger.info(f"📅 Reserving connector {connector_id} on {charge_point_id}")
    cp = manager.get_charge_points().get(charge_point_id)
    if not cp:
        raise HTTPException(status_code=404, detail="Charge point not connected.")
    response = await cp.reserve_now_req(connector_id, expiry_date, id_tag, reservation_id, parent_id_tag)
    return {"command": "ReserveNow", "result": response.status}

@router.post("/charge_points/{charge_point_id}/cancel_reservation")
async def cancel_reservation(charge_point_id: str, reservation_id: int):
    logger.info(f"❌ Cancelling reservation {reservation_id} on {charge_point_id}")
    cp = manager.get_charge_points().get(charge_point_id)
    if not cp:
        raise HTTPException(status_code=404, detail="Charge point not connected.")
    response = await cp.cancel_reservation_req(reservation_id)
    return {"command": "CancelReservation", "result": response.status}