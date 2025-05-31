from fastapi import FastAPI
from app.api.routes import router as api_router
from app.ws.websocket_handler import websocket_endpoint
from contextlib import asynccontextmanager
from app.db.database import init_db
from app.config.payment_config import configure_stripe, payment_settings
from app.services.payment_service import PaymentService
import logging

from fastapi.middleware.cors import CORSMiddleware

# Configure logger with explicit level
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ocpp-server")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle events."""
    print("🚀 LIFESPAN STARTING...")  # Add print for debugging
    logger.info("🚀 LIFESPAN STARTING...")
    
    try:
        # Initialize database
        print("📊 Initializing database...")
        logger.info("Initializing database...")
        init_db()
        print("✅ Database initialization complete")
        logger.info("Database initialization complete")
        
        # Configure Stripe
        print("💳 Configuring payment services...")
        logger.info("Configuring payment services...")
        configure_stripe()
        PaymentService.configure_stripe(payment_settings.stripe_secret_key)
        print("✅ Payment services configured")
        logger.info(f"Payment services configured for {payment_settings.environment} environment")
        
        # Application startup
        print("🎯 OCPP Server starting up")
        logger.info("OCPP Server starting up")
        
        yield
        
        # Application shutdown
        print("🛑 OCPP Server shutting down")
        logger.info("OCPP Server shutting down")
        
    except Exception as e:
        print(f"❌ Error in lifespan: {str(e)}")
        logger.error(f"Error during application startup: {str(e)}", exc_info=True)
        raise

app = FastAPI(
    title="OCPP Central System Server", 
    description="OCPP server with company, site, charger management and payment processing",
    version="1.0.0",
    lifespan=lifespan  # Make sure this is set
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(api_router)

# Add WebSocket endpoint
app.add_api_websocket_route("/api/v1/cs/{charge_point_id}", websocket_endpoint)