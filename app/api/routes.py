from fastapi import APIRouter, HTTPException
from app.ws.connection_manager import manager
import logging
import uuid

# Import our new routers
from app.api.company_routes import router as company_router
from app.api.site_routes import router as site_router, company_router as site_company_router
from app.api.charger_routes import router as charger_router, site_router as charger_site_router
from app.api.websocket_routes import router as websocket_router
from app.api.session_routes import router as session_router
from app.api.rfid_card_routes import router as rfid_card_router, company_router as rfid_company_router, driver_router as rfid_driver_router
from app.api.driver_routes import router as driver_router, company_router as driver_company_router
from app.api.site_group_routes import router as site_group_router, company_router as site_group_company_router
from app.api.driver_group_routes import router as driver_group_router, company_router as driver_group_company_router
from app.api.tariff_routes import router as tariff_router, company_router as tariff_company_router

router = APIRouter()
logger = logging.getLogger("ocpp.routes")

# Include our new routers
router.include_router(company_router)
router.include_router(site_router)
router.include_router(charger_router)
router.include_router(site_company_router)
router.include_router(charger_site_router)
router.include_router(websocket_router)
router.include_router(session_router)
router.include_router(rfid_card_router)
router.include_router(rfid_company_router)
router.include_router(rfid_driver_router)
router.include_router(driver_router)
router.include_router(driver_company_router)
router.include_router(site_group_router)
router.include_router(site_group_company_router)
router.include_router(driver_group_router)
router.include_router(driver_group_company_router)
router.include_router(tariff_router)
router.include_router(tariff_company_router)