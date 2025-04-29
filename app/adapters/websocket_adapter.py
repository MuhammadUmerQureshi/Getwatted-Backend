import asyncio
import logging
import json
from fastapi import WebSocket
from datetime import datetime

logger = logging.getLogger("ocpp.adapter")

class WebSocketAdapter:
    def __init__(self, websocket):
        self.websocket = websocket
        self.created_at = asyncio.get_event_loop().time()
        
    async def recv(self) -> str:
        message = await self.websocket.receive_text()
        try:
            parsed = json.loads(message)
            msg_type = parsed[0] if len(parsed) > 0 else "Unknown"
            msg_id = parsed[1] if len(parsed) > 1 else "Unknown"
            action = parsed[2] if len(parsed) > 2 else "Unknown"
            
            logger.info(f"⬅️  RECEIVED MESSAGE | Type: {msg_type} | ID: {msg_id} | Action: {action}")
            logger.info(f"⬅️  FULL MESSAGE: {message}")
            
            # Log timestamp for tracking latency
            now = datetime.now().isoformat()
            logger.info(f"⬅️  MESSAGE TIMESTAMP: {now}")
        except Exception as e:
            logger.warning(f"⚠️  Could not parse received message for logging: {str(e)}")
            logger.info(f"⬅️  RAW RECEIVED MESSAGE: {message}")
        
        return message
        
    async def send(self, message: str) -> None:
        try:
            parsed = json.loads(message)
            msg_type = parsed[0] if len(parsed) > 0 else "Unknown"
            msg_id = parsed[1] if len(parsed) > 1 else "Unknown"
            
            if msg_type == 2:  # Request from server to charge point
                action = parsed[2] if len(parsed) > 2 else "Unknown"
                logger.info(f"➡️  SENDING REQUEST | Type: {msg_type} | ID: {msg_id} | Action: {action}")
            elif msg_type == 3:  # Response to charge point request
                result = "Success" if len(parsed) > 2 and parsed[2] is not None else "Error"
                logger.info(f"➡️  SENDING RESPONSE | Type: {msg_type} | ID: {msg_id} | Result: {result}")
            
            logger.info(f"➡️  FULL MESSAGE: {message}")
            
            # Log timestamp for tracking latency
            now = datetime.now().isoformat() 
            logger.info(f"➡️  MESSAGE TIMESTAMP: {now}")
        except Exception as e:
            logger.warning(f"⚠️  Could not parse outgoing message for logging: {str(e)}")
            logger.info(f"➡️  RAW OUTGOING MESSAGE: {message}")
            
        await self.websocket.send_text(message)