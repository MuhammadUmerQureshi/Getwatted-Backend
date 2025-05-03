from fastapi import APIRouter, HTTPException
from app.ws.connection_manager import manager
import logging
import uuid

# Import our new routers
from app.api.company_routes import router as company_router
from app.api.site_routes import router as site_router, company_router as site_company_router
from app.api.charger_routes import router as charger_router, site_router as charger_site_router
from app.api.websocket_routes import router as websocket_router
router = APIRouter()
logger = logging.getLogger("ocpp.routes")

# Include our new routers
router.include_router(company_router)
router.include_router(site_router)
router.include_router(charger_router)
router.include_router(site_company_router)
router.include_router(charger_site_router)
router.include_router(websocket_router)
