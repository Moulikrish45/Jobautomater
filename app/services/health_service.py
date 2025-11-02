"""Health monitoring service for system components."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass, asdict
import aiohttp
import motor.motor_asyncio
from redis import asyncio as aioredis

from app.config import settings


logger = logging.getLogger(__name__)


class ServiceStatus(str, Enum):
    """Service health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheck:
    """Health check result."""
    service: str
    status: ServiceStatus
    message: str
    response_time: float
    timestamp: datetime
    details: Optional[Dict[str, Any]] = None


class HealthMonitor:
    """System health monitoring service."""
    
    def __init__(self):
        self.checks: Dict[str, HealthCheck] = {}
        self.monitoring_task: Optional[asyncio.Task] = None
        self._running = False
    
    async def start_monitoring(self):
        """Start continuous health monitoring."""
        if self._running:
            return
        
        self._running = True
        self.monitoring_task = asyncio.create_task(self._monitor_loop())
        logger.info("Health monitoring started")
    
    async def stop_monitoring(self):
        """Stop health monitoring."""
        self._running = False
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        logger.info("Health monitoring stopped")
    
    async def _monitor_loop(self):
        """Main monitoring loop."""
        while self._running:
            try:
                await self.run_all_checks()
                await asyncio.sleep(settings.health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health monitoring loop: {e}")
                await asyncio.sleep(5)  # Brief pause before retrying
    
    async def run_all_checks(self):
        """Run all health checks."""
        checks = [
            self.check_database(),
            self.check_redis(),
            self.check_ollama(),
            self.check_mcp_agents(),
            self.check_file_system(),
        ]
        
        results = await asyncio.gather(*checks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Health check failed: {result}")
            elif isinstance(result, HealthCheck):
                self.checks[result.service] = result
    
    async def check_database(self) -> HealthCheck:
        """Check MongoDB connection and basic operations."""
        start_time = datetime.now()
        
        try:
            # Create a test connection
            client = motor.motor_asyncio.AsyncIOMotorClient(
                settings.mongodb_url,
                serverSelectionTimeoutMS=int(settings.service_timeout * 1000)
            )
            
            # Test connection
            await client.admin.command('ping')
            
            # Test database access
            db = client[settings.database_name]
            await db.list_collection_names()
            
            response_time = (datetime.now() - start_time).total_seconds()
            
            return HealthCheck(
                service="mongodb",
                status=ServiceStatus.HEALTHY,
                message="Database connection successful",
                response_time=response_time,
                timestamp=datetime.now(),
                details={"url": settings.mongodb_url, "database": settings.database_name}
            )
            
        except Exception as e:
            response_time = (datetime.now() - start_time).total_seconds()
            return HealthCheck(
                service="mongodb",
                status=ServiceStatus.UNHEALTHY,
                message=f"Database connection failed: {str(e)}",
                response_time=response_time,
                timestamp=datetime.now(),
                details={"error": str(e)}
            )
    
    async def check_redis(self) -> HealthCheck:
        """Check Redis connection and basic operations."""
        start_time = datetime.now()
        
        try:
            redis = aioredis.from_url(
                settings.redis_url,
                socket_timeout=settings.service_timeout,
                socket_connect_timeout=settings.service_timeout
            )
            
            # Test connection
            await redis.ping()
            
            # Test basic operations
            test_key = "health_check_test"
            await redis.set(test_key, "test_value", ex=10)
            value = await redis.get(test_key)
            await redis.delete(test_key)
            
            if value != b"test_value":
                raise Exception("Redis read/write test failed")
            
            response_time = (datetime.now() - start_time).total_seconds()
            
            return HealthCheck(
                service="redis",
                status=ServiceStatus.HEALTHY,
                message="Redis connection successful",
                response_time=response_time,
                timestamp=datetime.now(),
                details={"url": settings.redis_url}
            )
            
        except Exception as e:
            response_time = (datetime.now() - start_time).total_seconds()
            return HealthCheck(
                service="redis",
                status=ServiceStatus.UNHEALTHY,
                message=f"Redis connection failed: {str(e)}",
                response_time=response_time,
                timestamp=datetime.now(),
                details={"error": str(e)}
            )
    
    async def check_ollama(self) -> HealthCheck:
        """Check Ollama AI service availability."""
        start_time = datetime.now()
        
        try:
            timeout = aiohttp.ClientTimeout(total=settings.service_timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # Check if Ollama is running
                async with session.get(f"{settings.ollama_host}/api/tags") as response:
                    if response.status == 200:
                        data = await response.json()
                        models = data.get("models", [])
                        
                        response_time = (datetime.now() - start_time).total_seconds()
                        
                        return HealthCheck(
                            service="ollama",
                            status=ServiceStatus.HEALTHY,
                            message="Ollama service available",
                            response_time=response_time,
                            timestamp=datetime.now(),
                            details={
                                "host": settings.ollama_host,
                                "models_count": len(models),
                                "default_model": settings.ollama_default_model
                            }
                        )
                    else:
                        raise Exception(f"Ollama returned status {response.status}")
                        
        except Exception as e:
            response_time = (datetime.now() - start_time).total_seconds()
            return HealthCheck(
                service="ollama",
                status=ServiceStatus.UNHEALTHY,
                message=f"Ollama service unavailable: {str(e)}",
                response_time=response_time,
                timestamp=datetime.now(),
                details={"error": str(e)}
            )
    
    async def check_mcp_agents(self) -> HealthCheck:
        """Check MCP agents status."""
        start_time = datetime.now()
        
        try:
            # Import here to avoid circular imports
            from app.mcp.coordinator import coordinator
            
            if not coordinator.is_running():
                raise Exception("MCP coordinator is not running")
            
            # Check agent status
            agent_status = await coordinator.get_agent_status()
            healthy_agents = sum(1 for status in agent_status.values() if status == "running")
            total_agents = len(agent_status)
            
            response_time = (datetime.now() - start_time).total_seconds()
            
            if healthy_agents == total_agents and total_agents > 0:
                status = ServiceStatus.HEALTHY
                message = f"All {total_agents} MCP agents running"
            elif healthy_agents > 0:
                status = ServiceStatus.DEGRADED
                message = f"{healthy_agents}/{total_agents} MCP agents running"
            else:
                status = ServiceStatus.UNHEALTHY
                message = "No MCP agents running"
            
            return HealthCheck(
                service="mcp_agents",
                status=status,
                message=message,
                response_time=response_time,
                timestamp=datetime.now(),
                details={
                    "total_agents": total_agents,
                    "healthy_agents": healthy_agents,
                    "agent_status": agent_status
                }
            )
            
        except Exception as e:
            response_time = (datetime.now() - start_time).total_seconds()
            return HealthCheck(
                service="mcp_agents",
                status=ServiceStatus.UNHEALTHY,
                message=f"MCP agents check failed: {str(e)}",
                response_time=response_time,
                timestamp=datetime.now(),
                details={"error": str(e)}
            )
    
    async def check_file_system(self) -> HealthCheck:
        """Check file system access and storage."""
        start_time = datetime.now()
        
        try:
            import os
            import tempfile
            from pathlib import Path
            
            # Check resume storage directory
            resume_path = Path(settings.resume_storage_path)
            resume_path.mkdir(parents=True, exist_ok=True)
            
            # Test write access
            test_file = resume_path / "health_check_test.txt"
            test_file.write_text("health check test")
            test_file.unlink()
            
            # Check available disk space
            stat = os.statvfs(resume_path)
            available_bytes = stat.f_bavail * stat.f_frsize
            available_gb = available_bytes / (1024**3)
            
            response_time = (datetime.now() - start_time).total_seconds()
            
            if available_gb < 1.0:  # Less than 1GB available
                status = ServiceStatus.DEGRADED
                message = f"Low disk space: {available_gb:.2f}GB available"
            else:
                status = ServiceStatus.HEALTHY
                message = f"File system accessible, {available_gb:.2f}GB available"
            
            return HealthCheck(
                service="file_system",
                status=status,
                message=message,
                response_time=response_time,
                timestamp=datetime.now(),
                details={
                    "resume_storage_path": str(resume_path),
                    "available_space_gb": round(available_gb, 2)
                }
            )
            
        except Exception as e:
            response_time = (datetime.now() - start_time).total_seconds()
            return HealthCheck(
                service="file_system",
                status=ServiceStatus.UNHEALTHY,
                message=f"File system check failed: {str(e)}",
                response_time=response_time,
                timestamp=datetime.now(),
                details={"error": str(e)}
            )
    
    def get_overall_status(self) -> ServiceStatus:
        """Get overall system health status."""
        if not self.checks:
            return ServiceStatus.UNKNOWN
        
        statuses = [check.status for check in self.checks.values()]
        
        if all(status == ServiceStatus.HEALTHY for status in statuses):
            return ServiceStatus.HEALTHY
        elif any(status == ServiceStatus.UNHEALTHY for status in statuses):
            return ServiceStatus.UNHEALTHY
        else:
            return ServiceStatus.DEGRADED
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get comprehensive health summary."""
        overall_status = self.get_overall_status()
        
        return {
            "status": overall_status,
            "timestamp": datetime.now().isoformat(),
            "services": {
                service: asdict(check) for service, check in self.checks.items()
            },
            "summary": {
                "total_services": len(self.checks),
                "healthy_services": sum(
                    1 for check in self.checks.values() 
                    if check.status == ServiceStatus.HEALTHY
                ),
                "degraded_services": sum(
                    1 for check in self.checks.values() 
                    if check.status == ServiceStatus.DEGRADED
                ),
                "unhealthy_services": sum(
                    1 for check in self.checks.values() 
                    if check.status == ServiceStatus.UNHEALTHY
                )
            }
        }


# Global health monitor instance
health_monitor = HealthMonitor()