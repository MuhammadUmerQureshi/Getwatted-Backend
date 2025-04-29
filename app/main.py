from fastapi import FastAPI
from app.api.routes import router as api_router
from app.ws.websocket_handler import websocket_endpoint
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    import logging
    logging.getLogger("ocpp-server").info("OCPP Server starting up")
    yield

app = FastAPI(title="OCPP Central System Server", lifespan=lifespan)

app.include_router(api_router)
app.add_api_websocket_route("/api/v1/cs/{charge_point_id}", websocket_endpoint)
