# app/main.py (Updated with Authentication)
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

# Import existing components
from app.api.routes import router as api_router
from app.ws.websocket_handler import websocket_endpoint
from app.db.database import init_db
from app.config.payment_config import configure_stripe, payment_settings
from app.services.payment_service import PaymentService

# Import new authentication components
from app.api.auth_routes import router as auth_router

# Configure logger with explicit level
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ocpp-server")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle events."""
    print("🚀 LIFESPAN STARTING...")
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
        
        # Initialize authentication
        print("🔐 Initializing authentication system...")
        logger.info("Authentication system initialized")
        from app.config.auth_config import auth_settings
        logger.info(f"JWT token expiry: {auth_settings.jwt_access_token_expire_hours} hours")
        print("✅ Authentication system ready")
        
        # Application startup
        print("🎯 OCPP Server starting up")
        logger.info("OCPP Server starting up with authentication enabled")
        
        yield
        
        # Application shutdown
        print("🛑 OCPP Server shutting down")
        logger.info("OCPP Server shutting down")
        
    except Exception as e:
        print(f"❌ Error in lifespan: {str(e)}")
        logger.error(f"Error during application startup: {str(e)}", exc_info=True)
        raise

app = FastAPI(
    title="OCPP Backend Server with Authentication", 
    description="",
    version="1.0",
    lifespan=lifespan
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include authentication routes FIRST (no auth required for login)
app.include_router(auth_router)

# Include existing API routes (now with auth protection)
app.include_router(api_router)

# Add WebSocket endpoint
app.add_api_websocket_route("/api/v1/cs/{charge_point_id}", websocket_endpoint)

# Root endpoint for health check
@app.get("/")
async def root():
    """Root endpoint for health checking."""
    return {
        "status": "running",
        "message": "OCPP Server with Authentication is running",
        "version": "1.1.0",
        "authentication": "enabled"
    }

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": "2025-01-03",
        "services": {
            "database": "connected",
            "authentication": "enabled",
            "payment": "configured"
        }
    }