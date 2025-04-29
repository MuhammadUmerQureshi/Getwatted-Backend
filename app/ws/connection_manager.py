from typing import Dict
from app.services.ChargePoint16 import ChargePoint16
import logging
import time
from datetime import datetime

logger = logging.getLogger("ocpp-server")

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, ChargePoint16] = {}
        self.connection_times: Dict[str, float] = {}
        logger.info(f"🚀 CONNECTION MANAGER INITIALIZED | Ready to accept connections")

    async def connect(self, charge_point_id: str, charge_point: ChargePoint16):
        connect_time = time.time()
        self.active_connections[charge_point_id] = charge_point
        self.connection_times[charge_point_id] = connect_time
        
        formatted_time = datetime.fromtimestamp(connect_time).strftime('%Y-%m-%d %H:%M:%S')
        
        logger.info(f"🔌 CHARGE POINT CONNECTED | ID: {charge_point_id} | Time: {formatted_time}")
        logger.info(f"📊 ACTIVE CONNECTIONS: {len(self.active_connections)} | IDs: {list(self.active_connections.keys())}")

    def disconnect(self, charge_point_id: str):
        if charge_point_id in self.active_connections:
            connect_time = self.connection_times.get(charge_point_id, 0)
            disconnect_time = time.time()
            session_duration = disconnect_time - connect_time
            
            del self.active_connections[charge_point_id]
            if charge_point_id in self.connection_times:
                del self.connection_times[charge_point_id]
                
            logger.info(f"🔌 CHARGE POINT DISCONNECTED | ID: {charge_point_id} | Duration: {session_duration:.2f} seconds")
            logger.info(f"📊 REMAINING CONNECTIONS: {len(self.active_connections)} | IDs: {list(self.active_connections.keys())}")
        else:
            logger.warning(f"⚠️ DISCONNECT CALLED FOR UNKNOWN CHARGE POINT | ID: {charge_point_id}")

    def get_charge_points(self):
        return self.active_connections
    
    def get_connection_stats(self):
        stats = {}
        current_time = time.time()
        
        for cp_id, connect_time in self.connection_times.items():
            duration = current_time - connect_time
            stats[cp_id] = {
                "connected_at": datetime.fromtimestamp(connect_time).isoformat(),
                "duration_seconds": duration,
                "duration_formatted": f"{int(duration//3600)}h {int((duration%3600)//60)}m {int(duration%60)}s"
            }
        
        return stats

manager = ConnectionManager()