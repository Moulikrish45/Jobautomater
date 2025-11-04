"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.config import settings
from app.database import connect_to_mongo, close_mongo_connection
from app.api.auth import router as auth_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Starting Job Application Automation Platform...")
    await connect_to_mongo()
    logger.info("Application startup complete")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    await close_mongo_connection()
    logger.info("Application shutdown complete")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    description="AI-powered job application automation platform",
    version="0.1.0",
    debug=settings.debug,
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # React dev servers
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Include API routers
app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])

# Add other routers now that auth is working
try:
    from app.api.users import router as users_router
    app.include_router(users_router, prefix="/api/v1/users", tags=["users"])
except ImportError as e:
    logger.warning(f"Users router not available: {e}")

try:
    from app.api.dashboard import router as dashboard_router
    app.include_router(dashboard_router, prefix="/api/v1/dashboard", tags=["dashboard"])
except ImportError as e:
    logger.warning(f"Dashboard router not available: {e}")

try:
    from app.api.applications import router as applications_router
    app.include_router(applications_router, prefix="/api/v1/applications", tags=["applications"])
except ImportError as e:
    logger.warning(f"Applications router not available: {e}")

# TODO: Add other routers as needed
# try:
#     from app.api.agents import router as agents_router
#     app.include_router(agents_router, prefix="/api/v1/agents", tags=["agents"])
# except ImportError as e:
#     logger.warning(f"Agents router not available: {e}")
#
# try:
#     from app.api.resume_builder import router as resume_router
#     app.include_router(resume_router, prefix="/api/v1/resume", tags=["resume"])
# except ImportError as e:
#     logger.warning(f"Resume router not available: {e}")

@app.get("/")
async def root():
    """Root endpoint for health check."""
    return {
        "message": "Job Application Automation Platform API",
        "version": "0.1.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


# Free job search API (if it exists)
try:
    from app.api.free_jobs import router as free_jobs_router
    app.include_router(free_jobs_router)
except ImportError:
    logger.info("Free jobs API not available")