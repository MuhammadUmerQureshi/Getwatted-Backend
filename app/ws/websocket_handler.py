from fastapi import WebSocket, WebSocketDisconnect, HTTPException
from app.adapters.websocket_adapter import WebSocketAdapter
from app.services.ChargePoint16 import ChargePoint16
from app.ws.connection_manager import manager
from app.db.database import execute_query
import logging
import time
import json
from datetime import datetime

logger = logging.getLogger("ocpp-server")

async def websocket_endpoint(websocket: WebSocket, charge_point_id: str):
    """
    WebSocket endpoint for OCPP charge points.
    
    Args:
        websocket: The WebSocket connection
        charge_point_id: The ID of the charge point (maps to ChargerName in the database)
    """
    connection_start_time = time.time()
    client_ip = websocket.client.host
    client_port = websocket.client.port
    
    logger.info(f"📡 INCOMING CONNECTION | Name: {charge_point_id} | IP: {client_ip}:{client_port}")
    
    # Log headers for debugging
    headers = websocket.headers
    logger.info(f"📋 CONNECTION HEADERS | {charge_point_id} | {headers}")
    
    requested_protocols = websocket.headers.get("sec-websocket-protocol", "")
    logger.info(f"🔄 REQUESTED PROTOCOLS | {charge_point_id} | {requested_protocols}")
    
    if "ocpp1.6" not in requested_protocols:
        logger.error(f"❌ PROTOCOL ERROR | {charge_point_id} | Missing OCPP1.6 protocol | Available: {requested_protocols}")
        return
    
    # Verify charger exists in database using ChargerName
    try:
        # Log database path to ensure we're connecting to the correct database
        logger.info(f"🔍 DATABASE PATH: {execute_query('PRAGMA database_list;')}")
        
        # List all chargers to debug
        all_chargers = execute_query("SELECT ChargerId, ChargerName FROM Chargers")
        logger.info(f"🔍 ALL CHARGERS IN DATABASE: {json.dumps([dict(c) for c in all_chargers])}")
        
        # Query the database for the charger using ChargerName
        logger.info(f"🔍 LOOKING FOR CHARGER WITH NAME: '{charge_point_id}'")
        charger = execute_query(
            "SELECT ChargerId, ChargerCompanyId, ChargerSiteId, ChargerName, ChargerEnabled FROM Chargers WHERE ChargerName = ?", 
            (charge_point_id,)
        )
        
        if not charger:
            logger.error(f"❌ CHARGER VERIFICATION FAILED | {charge_point_id} | Charger not found in database")
            # Try a case-insensitive search as a fallback
            logger.info(f"🔍 TRYING CASE-INSENSITIVE SEARCH FOR CHARGER: '{charge_point_id}'")
            charger = execute_query(
                "SELECT ChargerId, ChargerCompanyId, ChargerSiteId, ChargerName, ChargerEnabled FROM Chargers WHERE LOWER(ChargerName) = LOWER(?)", 
                (charge_point_id,)
            )
            if charger:
                logger.info(f"✅ FOUND CHARGER WITH CASE-INSENSITIVE SEARCH: {json.dumps([dict(c) for c in charger])}")
                # Update the charge_point_id to match the actual case in the database
                charge_point_id = charger[0]["ChargerName"]
                logger.info(f"🔄 UPDATED CHARGE POINT ID TO: '{charge_point_id}'")
            else:
                logger.error(f"❌ CHARGER NOT FOUND EVEN WITH CASE-INSENSITIVE SEARCH")
                await websocket.close(code=4001, reason="Charger not registered in system")
                return
        else:
            logger.info(f"✅ CHARGER FOUND: {json.dumps([dict(c) for c in charger])}")
        
        if not charger[0]["ChargerEnabled"]:
            logger.error(f"❌ CHARGER VERIFICATION FAILED | {charge_point_id} | Charger is disabled in database")
            await websocket.close(code=4002, reason="Charger is disabled")
            return
            
        # Get the actual charger ID from the database
        charger_id = charger[0]["ChargerId"]
        logger.info(f"✅ CHARGER VERIFIED | Name: '{charge_point_id}' | ID: {charger_id} | Company: {charger[0]['ChargerCompanyId']} | Site: {charger[0]['ChargerSiteId']}")
        
    except Exception as e:
        logger.error(f"❌ DATABASE ERROR | {charge_point_id} | {str(e)}")
        logger.exception(e)  # Log the full exception with traceback
        await websocket.close(code=4003, reason="Internal server error")
        return

    try:
        await websocket.accept(subprotocol="ocpp1.6")
        logger.info(f"✅ CONNECTION ACCEPTED | {charge_point_id} | Protocol: ocpp1.6")
        
        adapter = WebSocketAdapter(websocket)
        cp = ChargePoint16(charge_point_id, adapter)
        
        # Connection manager will update the database with online status
        await manager.connect(charge_point_id, cp)
        logger.info(f"📊 CHARGEPOINT REGISTERED | {charge_point_id} | Total active: {len(manager.get_charge_points())}")
        
        logger.info(f"🚀 STARTING OCPP SESSION | {charge_point_id}")
        await cp.start()

    except WebSocketDisconnect:
        connection_duration = time.time() - connection_start_time
        logger.info(f"👋 DISCONNECTED | {charge_point_id} | Duration: {connection_duration:.2f} seconds")
    except Exception as e:
        logger.error(f"⚠️ CONNECTION ERROR | {charge_point_id} | Error: {e}")
        logger.exception(e)  # Log the full exception with traceback
    finally:
        # Connection manager will update the database with offline status
        manager.disconnect(charge_point_id)
        logger.info(f"🗑️ CLEANUP COMPLETE | {charge_point_id} | Total active: {len(manager.get_charge_points())}")