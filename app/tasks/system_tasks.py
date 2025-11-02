"""System maintenance and monitoring Celery tasks."""

import asyncio
from datetime import datetime, timedelta
from celery import Task
import psutil
import gc

from app.celery_app import celery_app, mcp_agent_task
from app.services.logging_service import get_logger
from app.services.error_handling_service import error_handler, ErrorSeverity
from app.services.recovery_service import recovery_service
from app.services.notification_service import notification_service
from app.mcp.coordinator import coordinator
from app.config import settings


logger = get_logger(__name__)


@celery_app.task(bind=True)
def agent_health_check(self: Task):
    """Periodic health check for MCP agents."""
    try:
        # Run async health check
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(_async_agent_health_check())
        loop.close()
        
        return result
    except Exception as e:
        logger.error(f"Agent health check failed: {e}", component="system", operation="health_check")
        raise


async def _async_agent_health_check():
    """Async agent health check implementation."""
    try:
        agent_status = await coordinator.get_agent_status()
        
        failed_agents = []
        for agent_name, status in agent_status.items():
            if status.get("status") == "error":
                failed_agents.append(agent_name)
                
                # Trigger recovery for failed agents
                await recovery_service.handle_component_failure(
                    "mcp_agents",
                    "agent_failed",
                    {"agent_name": agent_name, "status": status}
                )
        
        return {
            "success": True,
            "total_agents": len(agent_status),
            "failed_agents": failed_agents,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Async agent health check failed: {e}")
        raise


@celery_app.task(bind=True)
def cleanup_old_results(self: Task):
    """Clean up old task results and error history."""
    try:
        # Run async cleanup
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(_async_cleanup_old_results())
        loop.close()
        
        return result
    except Exception as e:
        logger.error(f"Cleanup task failed: {e}", component="system", operation="cleanup")
        raise


async def _async_cleanup_old_results():
    """Async cleanup implementation."""
    try:
        cleanup_results = {}
        
        # Clean up error history
        initial_error_count = len(error_handler.error_history)
        error_handler.clear_error_history(older_than_hours=settings.error_history_retention_hours)
        final_error_count = len(error_handler.error_history)
        cleanup_results["errors_cleaned"] = initial_error_count - final_error_count
        
        # Force garbage collection
        collected = gc.collect()
        cleanup_results["garbage_collected"] = collected
        
        # Log memory usage
        memory_info = psutil.Process().memory_info()
        cleanup_results["memory_usage_mb"] = memory_info.rss / 1024 / 1024
        
        logger.info(
            "Cleanup completed successfully", 
            component="system", 
            operation="cleanup",
            extra_data=cleanup_results
        )
        
        return {
            "success": True,
            "message": "Cleanup completed successfully",
            "details": cleanup_results,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        await error_handler.handle_error(
            e,
            component="system",
            operation="cleanup",
            severity=ErrorSeverity.MEDIUM
        )
        raise


@celery_app.task(bind=True)
def system_health_report(self: Task):
    """Generate comprehensive system health report."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(_async_system_health_report())
        loop.close()
        
        return result
    except Exception as e:
        logger.error(f"System health report failed: {e}", component="system", operation="health_report")
        raise


async def _async_system_health_report():
    """Generate async system health report."""
    try:
        # Collect system metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Get error statistics
        error_stats = error_handler.get_error_statistics(hours=24)
        
        # Get circuit breaker status
        circuit_breaker_status = error_handler.get_circuit_breaker_status()
        
        # Get recovery service status
        recovery_status = recovery_service.get_system_status()
        
        # Check for critical conditions
        critical_conditions = []
        
        if cpu_percent > settings.cpu_alert_threshold:
            critical_conditions.append(f"High CPU usage: {cpu_percent:.1f}%")
        
        if memory.percent > settings.memory_alert_threshold:
            critical_conditions.append(f"High memory usage: {memory.percent:.1f}%")
        
        disk_percent = (disk.used / disk.total) * 100
        if disk_percent > settings.disk_alert_threshold:
            critical_conditions.append(f"High disk usage: {disk_percent:.1f}%")
        
        if error_stats["total_errors"] > 50:  # More than 50 errors in 24h
            critical_conditions.append(f"High error rate: {error_stats['total_errors']} errors in 24h")
        
        # Check circuit breaker states
        open_breakers = [
            name for name, status in circuit_breaker_status.items()
            if status.get("state") == "open"
        ]
        if open_breakers:
            critical_conditions.append(f"Open circuit breakers: {', '.join(open_breakers)}")
        
        health_report = {
            "timestamp": datetime.now().isoformat(),
            "system_metrics": {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "disk_percent": disk_percent,
                "available_memory_gb": memory.available / (1024**3)
            },
            "error_statistics": error_stats,
            "circuit_breaker_status": circuit_breaker_status,
            "recovery_status": recovery_status,
            "critical_conditions": critical_conditions,
            "health_score": _calculate_health_score(
                cpu_percent, memory.percent, disk_percent, 
                error_stats["total_errors"], len(open_breakers)
            )
        }
        
        # Send notification if there are critical conditions
        if critical_conditions:
            await notification_service.notify_system_error(
                user_id="system",
                error_type="system_health_alert",
                error_message=f"System health issues detected: {len(critical_conditions)} critical conditions",
                context={
                    "critical_conditions": critical_conditions,
                    "health_score": health_report["health_score"],
                    "timestamp": health_report["timestamp"]
                }
            )
        
        logger.info(
            f"System health report generated - Health Score: {health_report['health_score']}/100",
            component="system",
            operation="health_report",
            extra_data={
                "health_score": health_report["health_score"],
                "critical_conditions_count": len(critical_conditions)
            }
        )
        
        return {
            "success": True,
            "health_report": health_report
        }
        
    except Exception as e:
        await error_handler.handle_error(
            e,
            component="system",
            operation="health_report",
            severity=ErrorSeverity.HIGH
        )
        raise


def _calculate_health_score(cpu_percent: float, memory_percent: float, 
                          disk_percent: float, error_count: int, 
                          open_breakers: int) -> int:
    """Calculate overall system health score (0-100)."""
    score = 100
    
    # CPU penalty
    if cpu_percent > 90:
        score -= 30
    elif cpu_percent > 80:
        score -= 20
    elif cpu_percent > 70:
        score -= 10
    
    # Memory penalty
    if memory_percent > 95:
        score -= 25
    elif memory_percent > 85:
        score -= 15
    elif memory_percent > 75:
        score -= 8
    
    # Disk penalty
    if disk_percent > 95:
        score -= 20
    elif disk_percent > 90:
        score -= 10
    elif disk_percent > 80:
        score -= 5
    
    # Error penalty
    if error_count > 100:
        score -= 20
    elif error_count > 50:
        score -= 15
    elif error_count > 20:
        score -= 10
    elif error_count > 10:
        score -= 5
    
    # Circuit breaker penalty
    score -= open_breakers * 10
    
    return max(0, score)


@celery_app.task(bind=True)
def emergency_recovery(self: Task):
    """Emergency system recovery task."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(_async_emergency_recovery())
        loop.close()
        
        return result
    except Exception as e:
        logger.critical(f"Emergency recovery failed: {e}", component="system", operation="emergency_recovery")
        raise


async def _async_emergency_recovery():
    """Perform emergency system recovery."""
    try:
        recovery_actions = []
        
        # Force garbage collection
        collected = gc.collect()
        recovery_actions.append(f"Garbage collection: {collected} objects")
        
        # Reset all circuit breakers
        for breaker_name in error_handler.circuit_breakers:
            breaker = error_handler.circuit_breakers[breaker_name]
            breaker.failure_count = 0
            breaker.state = "closed"
            recovery_actions.append(f"Reset circuit breaker: {breaker_name}")
        
        # Clear degraded components
        degraded_count = len(recovery_service.degraded_components)
        recovery_service.degraded_components.clear()
        recovery_service.current_mode = "normal"
        recovery_actions.append(f"Cleared {degraded_count} degraded components")
        
        # Clear old error history
        initial_errors = len(error_handler.error_history)
        error_handler.clear_error_history(older_than_hours=1)  # Keep only last hour
        cleared_errors = initial_errors - len(error_handler.error_history)
        recovery_actions.append(f"Cleared {cleared_errors} old errors")
        
        logger.critical(
            "Emergency recovery completed",
            component="system",
            operation="emergency_recovery",
            extra_data={"actions": recovery_actions}
        )
        
        # Send notification
        await notification_service.notify_system_error(
            user_id="system",
            error_type="emergency_recovery",
            error_message="Emergency system recovery completed",
            context={
                "actions_taken": recovery_actions,
                "timestamp": datetime.now().isoformat()
            }
        )
        
        return {
            "success": True,
            "message": "Emergency recovery completed",
            "actions_taken": recovery_actions,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        await error_handler.handle_error(
            e,
            component="system",
            operation="emergency_recovery",
            severity=ErrorSeverity.CRITICAL
        )
        raise