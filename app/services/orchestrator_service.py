"""System orchestrator service for managing application lifecycle."""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass
import signal
import sys

from app.config import settings
from app.services.health_service import health_monitor, ServiceStatus


logger = logging.getLogger(__name__)


class SystemState(str, Enum):
    """System state enumeration."""
    STARTING = "starting"
    RUNNING = "running"
    DEGRADED = "degraded"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class ServiceInfo:
    """Service information."""
    name: str
    status: str
    started_at: Optional[datetime] = None
    error: Optional[str] = None


class SystemOrchestrator:
    """Main system orchestrator for managing application lifecycle."""
    
    def __init__(self):
        self.state = SystemState.STOPPED
        self.services: Dict[str, ServiceInfo] = {}
        self.startup_time: Optional[datetime] = None
        self.shutdown_handlers: List[callable] = []
        self._shutdown_event = asyncio.Event()
    
    async def startup(self):
        """Execute system startup sequence."""
        logger.info("Starting system orchestrator...")
        self.state = SystemState.STARTING
        self.startup_time = datetime.now()
        
        try:
            # Initialize core services in order
            await self._startup_database()
            await self._startup_redis()
            await self._startup_mcp_coordinator()
            await self._startup_health_monitor()
            await self._startup_notification_service()
            
            # Register shutdown handlers
            self._register_signal_handlers()
            
            self.state = SystemState.RUNNING
            logger.info("System startup completed successfully")
            
        except Exception as e:
            logger.error(f"System startup failed: {e}")
            self.state = SystemState.ERROR
            raise
    
    async def shutdown(self):
        """Execute graceful system shutdown sequence."""
        logger.info("Starting system shutdown...")
        self.state = SystemState.STOPPING
        
        try:
            # Execute shutdown handlers in reverse order
            for handler in reversed(self.shutdown_handlers):
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler()
                    else:
                        handler()
                except Exception as e:
                    logger.error(f"Error in shutdown handler: {e}")
            
            # Shutdown services in reverse order
            await self._shutdown_notification_service()
            await self._shutdown_health_monitor()
            await self._shutdown_mcp_coordinator()
            await self._shutdown_redis()
            await self._shutdown_database()
            
            self.state = SystemState.STOPPED
            logger.info("System shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during system shutdown: {e}")
            self.state = SystemState.ERROR
    
    async def _startup_database(self):
        """Initialize database connection."""
        logger.info("Initializing database connection...")
        
        try:
            from app.database import connect_to_mongo
            await connect_to_mongo()
            
            self.services["database"] = ServiceInfo(
                name="database",
                status="running",
                started_at=datetime.now()
            )
            logger.info("Database connection established")
            
        except Exception as e:
            self.services["database"] = ServiceInfo(
                name="database",
                status="error",
                error=str(e)
            )
            raise
    
    async def _startup_redis(self):
        """Initialize Redis connection."""
        logger.info("Initializing Redis connection...")
        
        try:
            # Redis connection is handled by individual services
            # Just verify it's accessible
            from redis import asyncio as aioredis
            redis = aioredis.from_url(settings.redis_url)
            await redis.ping()
            await redis.close()
            
            self.services["redis"] = ServiceInfo(
                name="redis",
                status="running",
                started_at=datetime.now()
            )
            logger.info("Redis connection verified")
            
        except Exception as e:
            self.services["redis"] = ServiceInfo(
                name="redis",
                status="error",
                error=str(e)
            )
            raise
    
    async def _startup_mcp_coordinator(self):
        """Initialize MCP coordinator and agents."""
        logger.info("Starting MCP coordinator...")
        
        try:
            from app.mcp.coordinator import coordinator
            await coordinator.start()
            
            self.services["mcp_coordinator"] = ServiceInfo(
                name="mcp_coordinator",
                status="running",
                started_at=datetime.now()
            )
            logger.info("MCP coordinator started")
            
        except Exception as e:
            self.services["mcp_coordinator"] = ServiceInfo(
                name="mcp_coordinator",
                status="error",
                error=str(e)
            )
            raise
    
    async def _startup_health_monitor(self):
        """Initialize health monitoring."""
        logger.info("Starting health monitor...")
        
        try:
            await health_monitor.start_monitoring()
            
            self.services["health_monitor"] = ServiceInfo(
                name="health_monitor",
                status="running",
                started_at=datetime.now()
            )
            logger.info("Health monitor started")
            
        except Exception as e:
            self.services["health_monitor"] = ServiceInfo(
                name="health_monitor",
                status="error",
                error=str(e)
            )
            raise
    
    async def _startup_notification_service(self):
        """Initialize notification service."""
        logger.info("Starting notification service...")
        
        try:
            from app.services.notification_service import initialize_notification_service
            await initialize_notification_service()
            
            self.services["notification_service"] = ServiceInfo(
                name="notification_service",
                status="running",
                started_at=datetime.now()
            )
            logger.info("Notification service started")
            
        except Exception as e:
            self.services["notification_service"] = ServiceInfo(
                name="notification_service",
                status="error",
                error=str(e)
            )
            # Don't raise for notification service - it's not critical
            logger.warning(f"Notification service failed to start: {e}")
    
    async def _shutdown_database(self):
        """Shutdown database connection."""
        logger.info("Shutting down database connection...")
        
        try:
            from app.database import close_mongo_connection
            await close_mongo_connection()
            
            if "database" in self.services:
                self.services["database"].status = "stopped"
            
        except Exception as e:
            logger.error(f"Error shutting down database: {e}")
    
    async def _shutdown_redis(self):
        """Shutdown Redis connections."""
        logger.info("Shutting down Redis connections...")
        
        try:
            # Redis connections are managed by individual services
            if "redis" in self.services:
                self.services["redis"].status = "stopped"
            
        except Exception as e:
            logger.error(f"Error shutting down Redis: {e}")
    
    async def _shutdown_mcp_coordinator(self):
        """Shutdown MCP coordinator."""
        logger.info("Shutting down MCP coordinator...")
        
        try:
            from app.mcp.coordinator import coordinator
            await coordinator.stop()
            
            if "mcp_coordinator" in self.services:
                self.services["mcp_coordinator"].status = "stopped"
            
        except Exception as e:
            logger.error(f"Error shutting down MCP coordinator: {e}")
    
    async def _shutdown_health_monitor(self):
        """Shutdown health monitor."""
        logger.info("Shutting down health monitor...")
        
        try:
            await health_monitor.stop_monitoring()
            
            if "health_monitor" in self.services:
                self.services["health_monitor"].status = "stopped"
            
        except Exception as e:
            logger.error(f"Error shutting down health monitor: {e}")
    
    async def _shutdown_notification_service(self):
        """Shutdown notification service."""
        logger.info("Shutting down notification service...")
        
        try:
            from app.services.notification_service import shutdown_notification_service
            await shutdown_notification_service()
            
            if "notification_service" in self.services:
                self.services["notification_service"].status = "stopped"
            
        except Exception as e:
            logger.error(f"Error shutting down notification service: {e}")
    
    def _register_signal_handlers(self):
        """Register signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating shutdown...")
            self._shutdown_event.set()
        
        # Register handlers for common shutdown signals
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        
        if hasattr(signal, 'SIGHUP'):
            signal.signal(signal.SIGHUP, signal_handler)
    
    def add_shutdown_handler(self, handler: callable):
        """Add a custom shutdown handler."""
        self.shutdown_handlers.append(handler)
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get comprehensive system information."""
        uptime = None
        if self.startup_time:
            uptime = (datetime.now() - self.startup_time).total_seconds()
        
        # Get health status
        health_summary = health_monitor.get_health_summary()
        overall_health = health_summary.get("status", ServiceStatus.UNKNOWN)
        
        # Determine system state based on health
        if self.state == SystemState.RUNNING:
            if overall_health == ServiceStatus.UNHEALTHY:
                current_state = SystemState.DEGRADED
            else:
                current_state = self.state
        else:
            current_state = self.state
        
        return {
            "system": {
                "state": current_state,
                "uptime_seconds": uptime,
                "startup_time": self.startup_time.isoformat() if self.startup_time else None,
                "version": settings.version,
                "environment": settings.environment
            },
            "services": {
                name: {
                    "status": service.status,
                    "started_at": service.started_at.isoformat() if service.started_at else None,
                    "error": service.error
                }
                for name, service in self.services.items()
            },
            "health": health_summary,
            "configuration": {
                "debug": settings.debug,
                "log_level": settings.log_level,
                "environment": settings.environment,
                "database": settings.database_name,
                "mcp_agents_enabled": True,
                "health_monitoring_enabled": True
            }
        }
    
    async def wait_for_shutdown(self):
        """Wait for shutdown signal."""
        await self._shutdown_event.wait()


# Global orchestrator instance
orchestrator = SystemOrchestrator()