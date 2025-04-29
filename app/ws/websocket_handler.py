from fastapi import WebSocket, WebSocketDisconnect
from app.adapters.websocket_adapter import WebSocketAdapter
from app.services.ChargePoint16 import ChargePoint16
from app.ws.connection_manager import manager
import logging
import time

logger = logging.getLogger("ocpp-server")

async def websocket_endpoint(websocket: WebSocket, charge_point_id: str):
    connection_start_time = time.time()
    client_ip = websocket.client.host
    client_port = websocket.client.port
    
    logger.info(f"📡 INCOMING CONNECTION | ID: {charge_point_id} | IP: {client_ip}:{client_port}")
    
    # Log headers for debugging
    headers = websocket.headers
    logger.info(f"📋 CONNECTION HEADERS | {charge_point_id} | {headers}")
    
    requested_protocols = websocket.headers.get("sec-websocket-protocol", "")
    logger.info(f"🔄 REQUESTED PROTOCOLS | {charge_point_id} | {requested_protocols}")
    
    if "ocpp1.6" not in requested_protocols:
        logger.error(f"❌ PROTOCOL ERROR | {charge_point_id} | Missing OCPP1.6 protocol | Available: {requested_protocols}")
        return

    try:
        await websocket.accept(subprotocol="ocpp1.6")
        logger.info(f"✅ CONNECTION ACCEPTED | {charge_point_id} | Protocol: ocpp1.6")
        
        adapter = WebSocketAdapter(websocket)
        cp = ChargePoint16(charge_point_id, adapter)
        
        await manager.connect(charge_point_id, cp)
        logger.info(f"📊 CHARGEPOINT REGISTERED | {charge_point_id} | Total active: {len(manager.get_charge_points())}")
        
        logger.info(f"🚀 STARTING OCPP SESSION | {charge_point_id}")
        await cp.start()

    except WebSocketDisconnect:
        connection_duration = time.time() - connection_start_time
        logger.info(f"👋 DISCONNECTED | {charge_point_id} | Duration: {connection_duration:.2f} seconds")
    except Exception as e:
        logger.error(f"⚠️ CONNECTION ERROR | {charge_point_id} | Error: {e}", exc_info=True)
    finally:
        manager.disconnect(charge_point_id)
        logger.info(f"🗑️ CLEANUP COMPLETE | {charge_point_id} | Total active: {len(manager.get_charge_points())}")