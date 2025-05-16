from fastapi import FastAPI
from app.api.routes import router as api_router
from app.ws.websocket_handler import websocket_endpoint
from contextlib import asynccontextmanager
from app.db.database import init_db
import logging

from fastapi.middleware.cors import CORSMiddleware

# Configure logger
logger = logging.getLogger("ocpp-server")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifecycle events.
    This runs when the application starts, initializes the database,
    and executes any cleanup when the server shuts down.
    """
    try:
        # Initialize database
        logger.info("Initializing database...")
        init_db()
        logger.info("Database initialization complete")
        
        # Application startup
        logger.info("OCPP Server starting up")
        yield
        # Application shutdown
        logger.info("OCPP Server shutting down")
    except Exception as e:
        logger.error(f"Error during application startup: {str(e)}", exc_info=True)
        raise

app = FastAPI(
    title="OCPP Central System Server", 
    description="OCPP server with company, site, and charger management",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Will update it to the IP address of the client in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(api_router)

# Add WebSocket endpoint
app.add_api_websocket_route("/api/v1/cs/{charge_point_id}", websocket_endpoint)