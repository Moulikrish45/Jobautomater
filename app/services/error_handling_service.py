"""Comprehensive error handling service with circuit breaker pattern."""

import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable, List, Union
from enum import Enum
from dataclasses import dataclass, asdict
import traceback
from functools import wraps
import aiohttp

from app.config import settings


logger = logging.getLogger(__name__)


class ErrorSeverity(str, Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CircuitState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class ErrorInfo:
    """Error information structure."""
    error_id: str
    timestamp: datetime
    severity: ErrorSeverity
    component: str
    operation: str
    error_type: str
    message: str
    details: Dict[str, Any]
    stack_trace: Optional[str] = None
    user_id: Optional[str] = None
    correlation_id: Optional[str] = None


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""
    failure_threshold: int = 5
    recovery_timeout: int = 60  # seconds
    expected_exception: type = Exception
    name: str = "default"


class CircuitBreaker:
    """Circuit breaker implementation for fault tolerance."""
    
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = CircuitState.CLOSED
        self._lock = asyncio.Lock()
    
    async def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        async with self._lock:
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                else:
                    raise Exception(f"Circuit breaker {self.config.name} is OPEN")
            
            try:
                result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
                await self._on_success()
                return result
            except self.config.expected_exception as e:
                await self._on_failure()
                raise
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt reset."""
        if self.last_failure_time is None:
            return True
        
        return (datetime.now() - self.last_failure_time).total_seconds() > self.config.recovery_timeout
    
    async def _on_success(self):
        """Handle successful operation."""
        self.failure_count = 0
        self.state = CircuitState.CLOSED
    
    async def _on_failure(self):
        """Handle failed operation."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.failure_count >= self.config.failure_threshold:
            self.state = CircuitState.OPEN
    
    def get_state(self) -> Dict[str, Any]:
        """Get circuit breaker state information."""
        return {
            "name": self.config.name,
            "state": self.state,
            "failure_count": self.failure_count,
            "failure_threshold": self.config.failure_threshold,
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None
        }


class ErrorHandlingService:
    """Comprehensive error handling service."""
    
    def __init__(self):
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.error_history: List[ErrorInfo] = []
        self.notification_handlers: List[Callable] = []
        self.recovery_strategies: Dict[str, Callable] = {}
        self._setup_default_circuit_breakers()
    
    def _setup_default_circuit_breakers(self):
        """Setup default circuit breakers for common operations."""
        # Database operations
        self.circuit_breakers["database"] = CircuitBreaker(
            CircuitBreakerConfig(
                name="database",
                failure_threshold=3,
                recovery_timeout=30
            )
        )
        
        # External API calls
        self.circuit_breakers["external_api"] = CircuitBreaker(
            CircuitBreakerConfig(
                name="external_api",
                failure_threshold=5,
                recovery_timeout=60
            )
        )
        
        # AI model operations
        self.circuit_breakers["ai_model"] = CircuitBreaker(
            CircuitBreakerConfig(
                name="ai_model",
                failure_threshold=3,
                recovery_timeout=120
            )
        )
        
        # File system operations
        self.circuit_breakers["file_system"] = CircuitBreaker(
            CircuitBreakerConfig(
                name="file_system",
                failure_threshold=3,
                recovery_timeout=30
            )
        )
    
    async def handle_error(
        self,
        error: Exception,
        component: str,
        operation: str,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        user_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> ErrorInfo:
        """Handle and log error with comprehensive information."""
        
        error_id = f"{component}_{operation}_{datetime.now().timestamp()}"
        
        error_info = ErrorInfo(
            error_id=error_id,
            timestamp=datetime.now(),
            severity=severity,
            component=component,
            operation=operation,
            error_type=type(error).__name__,
            message=str(error),
            details=additional_context or {},
            stack_trace=traceback.format_exc(),
            user_id=user_id,
            correlation_id=correlation_id
        )
        
        # Store error in history
        self.error_history.append(error_info)
        
        # Log error with structured format
        await self._log_structured_error(error_info)
        
        # Send notifications for critical errors
        if severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            await self._send_error_notifications(error_info)
        
        # Attempt recovery if strategy exists
        if component in self.recovery_strategies:
            try:
                await self.recovery_strategies[component](error_info)
            except Exception as recovery_error:
                logger.error(f"Recovery strategy failed for {component}: {recovery_error}")
        
        return error_info
    
    async def _log_structured_error(self, error_info: ErrorInfo):
        """Log error with structured format."""
        log_data = {
            "error_id": error_info.error_id,
            "timestamp": error_info.timestamp.isoformat(),
            "severity": error_info.severity,
            "component": error_info.component,
            "operation": error_info.operation,
            "error_type": error_info.error_type,
            "message": error_info.message,
            "details": error_info.details,
            "user_id": error_info.user_id,
            "correlation_id": error_info.correlation_id
        }
        
        if settings.enable_json_logging:
            logger.error(json.dumps(log_data))
        else:
            logger.error(
                f"[{error_info.severity.upper()}] {error_info.component}.{error_info.operation}: "
                f"{error_info.message} (ID: {error_info.error_id})"
            )
            
            if error_info.stack_trace and settings.debug:
                logger.error(f"Stack trace: {error_info.stack_trace}")
    
    async def _send_error_notifications(self, error_info: ErrorInfo):
        """Send error notifications to configured handlers."""
        for handler in self.notification_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(error_info)
                else:
                    handler(error_info)
            except Exception as e:
                logger.error(f"Error notification handler failed: {e}")
    
    def add_notification_handler(self, handler: Callable):
        """Add error notification handler."""
        self.notification_handlers.append(handler)
    
    def add_recovery_strategy(self, component: str, strategy: Callable):
        """Add recovery strategy for component."""
        self.recovery_strategies[component] = strategy
    
    async def execute_with_circuit_breaker(
        self,
        circuit_name: str,
        func: Callable,
        *args,
        **kwargs
    ):
        """Execute function with circuit breaker protection."""
        if circuit_name not in self.circuit_breakers:
            raise ValueError(f"Circuit breaker '{circuit_name}' not found")
        
        circuit_breaker = self.circuit_breakers[circuit_name]
        return await circuit_breaker.call(func, *args, **kwargs)
    
    def get_circuit_breaker_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all circuit breakers."""
        return {
            name: breaker.get_state()
            for name, breaker in self.circuit_breakers.items()
        }
    
    def get_error_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """Get error statistics for specified time period."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_errors = [
            error for error in self.error_history
            if error.timestamp > cutoff_time
        ]
        
        # Group by component and severity
        component_stats = {}
        severity_stats = {severity.value: 0 for severity in ErrorSeverity}
        
        for error in recent_errors:
            # Component statistics
            if error.component not in component_stats:
                component_stats[error.component] = {
                    "total": 0,
                    "by_severity": {severity.value: 0 for severity in ErrorSeverity}
                }
            
            component_stats[error.component]["total"] += 1
            component_stats[error.component]["by_severity"][error.severity] += 1
            
            # Overall severity statistics
            severity_stats[error.severity] += 1
        
        return {
            "time_period_hours": hours,
            "total_errors": len(recent_errors),
            "component_statistics": component_stats,
            "severity_statistics": severity_stats,
            "circuit_breaker_status": self.get_circuit_breaker_status()
        }
    
    def clear_error_history(self, older_than_hours: int = 168):  # 7 days default
        """Clear old error history."""
        cutoff_time = datetime.now() - timedelta(hours=older_than_hours)
        self.error_history = [
            error for error in self.error_history
            if error.timestamp > cutoff_time
        ]


# Decorator for automatic error handling
def handle_errors(
    component: str,
    operation: str,
    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    circuit_breaker: Optional[str] = None,
    retry_attempts: int = 0,
    retry_delay: float = 1.0
):
    """Decorator for automatic error handling with optional circuit breaker and retry logic."""
    
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(retry_attempts + 1):
                try:
                    if circuit_breaker:
                        return await error_handler.execute_with_circuit_breaker(
                            circuit_breaker, func, *args, **kwargs
                        )
                    else:
                        return await func(*args, **kwargs)
                        
                except Exception as e:
                    last_exception = e
                    
                    # Handle error
                    await error_handler.handle_error(
                        e, component, operation, severity
                    )
                    
                    # Retry logic
                    if attempt < retry_attempts:
                        await asyncio.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                        continue
                    else:
                        raise
            
            # This should never be reached, but just in case
            if last_exception:
                raise last_exception
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # For sync functions, we can't await, so we schedule the error handling
                asyncio.create_task(
                    error_handler.handle_error(e, component, operation, severity)
                )
                raise
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


# Email notification handler
async def email_notification_handler(error_info: ErrorInfo):
    """Send email notification for critical errors."""
    if not settings.email_notifications_enabled:
        return
    
    try:
        # Import notification service to avoid circular imports
        from app.services.notification_service import notification_service
        
        # Send notification through the notification service
        await notification_service.notify_system_error(
            user_id="system",  # System-wide error
            error_type=error_info.error_type,
            error_message=f"[{error_info.severity.upper()}] {error_info.component}.{error_info.operation}: {error_info.message}",
            context={
                "error_id": error_info.error_id,
                "component": error_info.component,
                "operation": error_info.operation,
                "timestamp": error_info.timestamp.isoformat(),
                "details": error_info.details
            }
        )
        
        logger.info(f"Email notification queued for error: {error_info.error_id}")
        
    except Exception as e:
        logger.error(f"Failed to send email notification for error {error_info.error_id}: {e}")


# Webhook notification handler
async def webhook_notification_handler(error_info: ErrorInfo):
    """Send webhook notification for critical errors."""
    if not settings.webhook_notifications_enabled:
        return
    
    try:
        webhook_payload = {
            "error_id": error_info.error_id,
            "timestamp": error_info.timestamp.isoformat(),
            "severity": error_info.severity,
            "component": error_info.component,
            "operation": error_info.operation,
            "error_type": error_info.error_type,
            "message": error_info.message,
            "details": error_info.details,
            "user_id": error_info.user_id,
            "correlation_id": error_info.correlation_id
        }
        
        # Send webhook using aiohttp
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            if hasattr(settings, 'webhook_url') and settings.webhook_url:
                async with session.post(
                    settings.webhook_url,
                    json=webhook_payload,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    if response.status == 200:
                        logger.info(f"Webhook notification sent for error: {error_info.error_id}")
                    else:
                        logger.warning(f"Webhook notification failed with status {response.status} for error: {error_info.error_id}")
            else:
                logger.debug(f"Webhook URL not configured, skipping notification for error: {error_info.error_id}")
                
    except Exception as e:
        logger.error(f"Failed to send webhook notification for error {error_info.error_id}: {e}")


# Global error handler instance
error_handler = ErrorHandlingService()

# Add default notification handlers
error_handler.add_notification_handler(email_notification_handler)
error_handler.add_notification_handler(webhook_notification_handler)